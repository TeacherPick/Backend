import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Annotated, TypeVar

from fastapi import APIRouter, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import Field, TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.common import FILE_RESPONSES, Id, PageNumber, PageSize, SearchText
from app.core import AppError
from app.dependencies import Db, User, authenticate, require_user
from app.repositories.dm import room_page, room_versions, unread_count
from app.schemas import EnterRoom, ExitRoom, HistoryRead, MessageRead, Page, RoomCreate, RoomRead, SendMessage
from app.services import dm
from app.services.auth import login_required
from app.services.files import download

router = APIRouter(prefix="/dm", tags=["DM"])
logger = logging.getLogger(__name__)
PROTOCOL = "instructor.dm.v1"
MAX_FRAME_BYTES = 7 * 1024 * 1024
commands = TypeAdapter(Annotated[EnterRoom | ExitRoom | SendMessage, Field(discriminator="type")])
T = TypeVar("T")


@router.post("/rooms")
def open_room(data: RoomCreate, db: Db, principal: User) -> dict[str, int]:
    return {"room_id": dm.open_room(db, principal.account.id, data.recipient_id)}


@router.get("/rooms")
def list_rooms(db: Db, principal: User, page: PageNumber = 1, size: PageSize = 20, q: SearchText = None) -> Page[RoomRead]:
    return room_page(db, principal.account.id, page, size, q=q)


@router.get("/unread")
def unread(db: Db, principal: User) -> dict[str, int]:
    return {"total": unread_count(db, principal.account.id)}


@router.get("/rooms/{room_id}")
def room(room_id: Id, db: Db, principal: User) -> RoomRead:
    result = room_page(db, principal.account.id, 1, 1, room_id=room_id)
    if not result.items:
        raise AppError(404, "room_not_found", "존재하지 않는 대화방입니다.")
    return result.items[0]


@router.get("/rooms/{room_id}/messages")
def history(
    room_id: Id, db: Db, principal: User, size: PageSize = 50,
    before_id: Annotated[int | None, Query(gt=0, le=9223372036854775807)] = None,
) -> HistoryRead:
    return dm.history(db, principal.account.id, room_id, before_id, size)


@router.get(
    "/rooms/{room_id}/messages/{message_id}/attachment", response_class=Response, responses=FILE_RESPONSES,
)
def attachment(room_id: Id, message_id: Id, db: Db, principal: User) -> Response:
    return download(dm.download_attachment(db, principal.account.id, room_id, message_id))


@router.delete("/rooms/{room_id}", status_code=204)
def leave_room(room_id: Id, db: Db, principal: User) -> None:
    dm.leave_room(db, principal.account.id, room_id)


def ws_credentials(socket: WebSocket) -> tuple[str, str | None]:
    origin = socket.headers.get("origin")
    origins = socket.app.state.settings.cors_origins
    scheme = "https" if socket.url.scheme == "wss" else "http"
    same_origin = f"{scheme}://{socket.headers.get('host', '')}"
    if origin and origin not in (*origins, same_origin):
        raise AppError(403, "invalid_origin", "허용되지 않은 접속 출처입니다.")

    protocols = socket.scope.get("subprotocols", [])
    authorization = socket.headers.get("authorization", "").split()
    if len(authorization) == 2 and authorization[0].lower() == "bearer":
        return authorization[1], PROTOCOL if PROTOCOL in protocols else None
    if len(protocols) == 2 and protocols[0] == PROTOCOL:
        return protocols[1], PROTOCOL
    raise login_required()


def _poll(
    db: Session, account_id: int, selected: int | None, cursor: int,
) -> tuple[dict[int, int], list[MessageRead], bool]:
    versions = room_versions(db, account_id)
    if selected is None or selected not in versions:
        return versions, [], selected is not None
    if versions[selected] <= cursor:
        return versions, [], False
    try:
        return versions, dm.new_messages(db, account_id, selected, cursor), False
    except AppError as exc:
        if exc.code != "room_not_found":
            raise
        return versions, [], True


@router.websocket("/ws")
async def socket_endpoint(socket: WebSocket) -> None:
    try:
        token, subprotocol = ws_credentials(socket)
    except AppError as exc:
        await socket.close(code=4401 if exc.status == 401 else 4403)
        return

    def run(operation: Callable[..., T], *args) -> T:
        with socket.app.state.sessions() as db:
            account_id = require_user(authenticate(db, token)).account.id
            return operation(db, account_id, *args)

    try:
        versions = await run_in_threadpool(run, room_versions)
    except AppError as exc:
        await socket.close(code=4401 if exc.status == 401 else 4403)
        return
    except SQLAlchemyError:
        logger.error("Database error during DM authentication")
        await socket.close(code=1011)
        return

    await socket.accept(subprotocol=subprotocol)
    await socket.send_json({"type": "ready"})
    pending = asyncio.create_task(socket.receive())
    selected = None
    cursor = 0
    loop = asyncio.get_running_loop()
    next_poll = loop.time() + 1

    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=max(0, next_poll - loop.time()))
            if done:
                frame = pending.result()
                if frame["type"] == "websocket.disconnect":
                    return
                raw = frame.get("text")
                if raw is None:
                    await socket.close(code=1003)
                    return
                if len(raw.encode()) > MAX_FRAME_BYTES:
                    await socket.close(code=1009)
                    return
                try:
                    command = commands.validate_json(raw)
                    if isinstance(command, EnterRoom):
                        cursor = await run_in_threadpool(run, dm.enter_room, command.room_id)
                        selected = command.room_id
                        await socket.send_json({"type": "room.entered", "room_id": selected, "after_id": cursor})
                    elif isinstance(command, ExitRoom):
                        await socket.send_json({"type": "room.exited", "room_id": selected})
                        selected, cursor = None, 0
                    else:
                        sent = await run_in_threadpool(run, dm.send_message, command)
                        await socket.send_json({"type": "message.ack", "message": sent.model_dump(mode="json")})
                except ValidationError:
                    await socket.send_json({"type": "error", "code": "invalid_command", "message": "메시지 형식을 확인해주세요."})
                except AppError as exc:
                    if exc.status == 401:
                        await socket.close(code=4401)
                        return
                    await socket.send_json({"type": "error", "code": exc.code, "message": exc.message})
                pending = asyncio.create_task(socket.receive())
            if loop.time() >= next_poll:
                latest, incoming, room_closed = await run_in_threadpool(run, _poll, selected, cursor)
                for room_id, version in latest.items():
                    if room_id != selected and version > versions.get(room_id, 0):
                        await socket.send_json({"type": "room.updated", "room_id": room_id, "latest_message_id": version})
                versions = latest
                for message in incoming:
                    await socket.send_json({"type": "message.created", "message": message.model_dump(mode="json")})
                    cursor = message.id
                if room_closed:
                    await socket.send_json({"type": "room.closed", "room_id": selected})
                    selected, cursor = None, 0
                next_poll = loop.time() + 1
    except WebSocketDisconnect:
        pass
    except AppError:
        await socket.close(code=4401)
    except SQLAlchemyError:
        logger.error("Database error during DM operation")
        await socket.close(code=1011)
    finally:
        pending.cancel()
        with suppress(asyncio.CancelledError, WebSocketDisconnect):
            await pending
