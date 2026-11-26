import base64
import binascii
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session, undefer

from app.core import AppError
from app.models import Message, MessageAttachment, Room
from app.repositories.accounts import lock_active_account
from app.repositories.dm import get_room, message_read, messages, side
from app.schemas import HistoryRead, MessageRead, SendMessage
from app.services.auth import login_required
from app.services.files import validate_file


def open_room(db: Session, account_id: int, recipient_id: int) -> int:
    if account_id == recipient_id:
        raise AppError(422, "self_message", "자신과 대화방을 만들 수 없습니다.")
    if lock_active_account(db, account_id) is None:
        raise login_required()
    target = lock_active_account(db, recipient_id)
    if target is None or target.role == "admin":
        raise AppError(404, "recipient_unavailable", "대화할 수 없는 상대입니다.")
    low, high = sorted((account_id, recipient_id))
    if target.role == "instructor":
        stmt = insert(Room).values(low_id=low, high_id=high)
        db.execute(stmt.on_duplicate_key_update(low_id=stmt.inserted.low_id))
    room = db.scalar(
        select(Room).where(Room.low_id == low, Room.high_id == high).with_for_update()
    )
    if room is None:
        raise AppError(403, "instructor_recipient_required", "강사에게만 새 문의를 시작할 수 있습니다.")
    setattr(room, f"{side(room, account_id)}_active", True)
    room_id = room.id
    db.commit()
    return room_id


def leave_room(db: Session, account_id: int, room_id: int) -> None:
    room, member = get_room(db, room_id, account_id, lock=True)
    setattr(room, f"{member}_active", False)
    setattr(room, f"{member}_read_id", room.last_message_id)
    setattr(room, f"{member}_hidden_through", room.last_message_id)
    db.commit()


def history(
    db: Session, account_id: int, room_id: int, before_id: int | None, size: int,
) -> HistoryRead:
    room, member = get_room(db, room_id, account_id)
    filters = [Message.room_id == room_id, Message.id > getattr(room, f"{member}_hidden_through")]
    if before_id is not None:
        filters.append(Message.id < before_id)
    rows = messages(db, filters, size + 1, newest_first=True)
    page = rows[:size]
    return HistoryRead(
        items=list(reversed(page)), next_before_id=page[-1].id if len(rows) > size else None,
    )


def download_attachment(db: Session, account_id: int, room_id: int, message_id: int) -> MessageAttachment:
    room, member = get_room(db, room_id, account_id)
    attachment = db.scalar(
        select(MessageAttachment)
        .join(Message, Message.id == MessageAttachment.message_id)
        .where(
            Message.room_id == room_id, Message.id == message_id,
            Message.id > getattr(room, f"{member}_hidden_through"),
        )
        .options(undefer(MessageAttachment.data))
    )
    if attachment is None:
        raise AppError(404, "attachment_not_found", "존재하지 않는 첨부파일입니다.")
    return attachment


def enter_room(db: Session, account_id: int, room_id: int) -> int:
    room, member = get_room(db, room_id, account_id, lock=True)
    cursor = room.last_message_id
    setattr(room, f"{member}_read_id", cursor)
    db.commit()
    return cursor


def new_messages(db: Session, account_id: int, room_id: int, after_id: int) -> list[MessageRead]:
    room, member = get_room(db, room_id, account_id)
    if room.last_message_id <= after_id:
        return []
    room, member = get_room(db, room_id, account_id, lock=True)
    rows = messages(
        db, [Message.room_id == room_id, Message.id > max(after_id, getattr(room, f"{member}_hidden_through"))],
        100, newest_first=False,
    )
    if rows:
        read = f"{member}_read_id"
        setattr(room, read, max(getattr(room, read), rows[-1].id))
    db.commit()
    return rows


def send_message(db: Session, account_id: int, data: SendMessage) -> MessageRead:
    room, member = get_room(db, data.room_id, account_id)
    file = None
    if data.attachment:
        try:
            decoded = base64.b64decode(data.attachment.data_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise AppError(422, "invalid_file_encoding", "파일을 Base64로 인코딩해주세요.") from exc
        file = validate_file(data.attachment.filename, decoded)
    if lock_active_account(db, account_id) is None:
        raise login_required()
    other_id = room.high_id if member == "low" else room.low_id
    other = lock_active_account(db, other_id)
    room, member = get_room(db, data.room_id, account_id, lock=True)
    client_id = str(data.client_id)
    prior = messages(db, [
        Message.room_id == room.id, Message.sender_id == account_id, Message.client_id == client_id,
    ], 1, newest_first=False)
    if prior:
        if prior[0].id <= getattr(room, f"{member}_hidden_through"):
            raise AppError(409, "message_id_already_used", "새 메시지 ID를 사용해주세요.")
        return prior[0]
    if other is None:
        raise AppError(409, "recipient_unavailable", "대화할 수 없는 상대입니다.")
    message = Message(room_id=room.id, sender_id=account_id, client_id=client_id, body=data.body)
    db.add(message)
    db.flush()
    if file:
        db.add(MessageAttachment(message_id=message.id, **asdict(file)))
    room.last_message_id = message.id
    result = message_read(
        message, file.filename if file else None, file.media_type if file else None, file.size if file else None,
    )
    db.commit()
    return result
