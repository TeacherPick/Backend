from collections.abc import Sequence

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core import AppError
from app.models import Account, Message, MessageAttachment, Room
from app.schemas import AttachmentRead, Author, MessageRead, Page, RoomRead


def side(room: Room, account_id: int) -> str:
    if account_id == room.low_id:
        return "low"
    if account_id == room.high_id:
        return "high"
    raise AppError(404, "room_not_found", "존재하지 않는 대화방입니다.")


def get_room(db: Session, room_id: int, account_id: int, *, lock: bool = False) -> tuple[Room, str]:
    statement = select(Room).where(Room.id == room_id, visible_rooms(account_id))
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    room = db.scalar(statement)
    if room is None:
        raise AppError(404, "room_not_found", "존재하지 않는 대화방입니다.")
    return room, side(room, account_id)


def visible_rooms(account_id: int):
    return or_(
        and_(Room.low_id == account_id, Room.low_active.is_(True)),
        and_(Room.high_id == account_id, Room.high_active.is_(True)),
    )


def _message_columns():
    return (MessageAttachment.filename, MessageAttachment.media_type, MessageAttachment.size)


def message_read(
    message: Message, filename: str | None, media_type: str | None, size: int | None,
) -> MessageRead:
    attachment = AttachmentRead(filename=filename, media_type=media_type, size=size) if filename else None
    return MessageRead(
        id=message.id, room_id=message.room_id, sender_id=message.sender_id, client_id=message.client_id,
        body=message.body, attachment=attachment, created_at=message.created_at,
    )


def messages(db: Session, filters: Sequence, limit: int, *, newest_first: bool) -> list[MessageRead]:
    rows = db.execute(
        select(Message, *_message_columns())
        .outerjoin(MessageAttachment, MessageAttachment.message_id == Message.id)
        .where(*filters).order_by(Message.id.desc() if newest_first else Message.id).limit(limit)
    )
    return [message_read(*row) for row in rows]


def room_page(
    db: Session, account_id: int, page: int, size: int, *, q: str | None = None, room_id: int | None = None,
) -> Page[RoomRead]:
    visible = visible_rooms(account_id)
    counterpart = case((Room.low_id == account_id, Room.high_id), else_=Room.low_id)
    filters = [visible]
    if q:
        filters.append(Account.name.contains(q, autoescape=True))
    if room_id is not None:
        filters.append(Room.id == room_id)
    total = db.scalar(select(func.count()).select_from(Room).join(Account, Account.id == counterpart).where(*filters))
    hidden_through = case((Room.low_id == account_id, Room.low_hidden_through), else_=Room.high_hidden_through)
    read_id = case((Room.low_id == account_id, Room.low_read_id), else_=Room.high_read_id)
    unread_message = aliased(Message)
    unread = select(func.count()).where(
        unread_message.room_id == Room.id, unread_message.sender_id != account_id,
        unread_message.id > read_id, unread_message.id > hidden_through,
    ).correlate(Room).scalar_subquery()
    statement = (
        select(Room, Account.id, Account.name, Message, *_message_columns(), unread)
        .join(Account, Account.id == counterpart)
        .outerjoin(Message, and_(Message.id == Room.last_message_id, Message.id > hidden_through))
        .outerjoin(MessageAttachment, MessageAttachment.message_id == Message.id)
        .where(*filters)
        .order_by(func.coalesce(Message.created_at, Room.created_at).desc(), Room.id.desc())
        .offset((page - 1) * size).limit(size)
    )
    items = [
        RoomRead(
            id=room.id, counterpart=Author(id=other_id, name=name),
            last_message=message_read(msg, filename, media_type, file_size) if msg else None,
            unread_count=unread_count, created_at=room.created_at,
        )
        for room, other_id, name, msg, filename, media_type, file_size, unread_count in db.execute(statement)
    ]
    return Page[RoomRead](items=items, total=total, page=page, size=size)


def unread_count(db: Session, account_id: int) -> int:
    read_id = case((Room.low_id == account_id, Room.low_read_id), else_=Room.high_read_id)
    hidden_through = case((Room.low_id == account_id, Room.low_hidden_through), else_=Room.high_hidden_through)
    return db.scalar(select(func.count()).select_from(Room).join(Message, Message.room_id == Room.id).where(
        visible_rooms(account_id), Message.sender_id != account_id,
        Message.id > read_id, Message.id > hidden_through,
    ))


def room_versions(db: Session, account_id: int) -> dict[int, int]:
    return dict(db.execute(
        select(Room.id, Room.last_message_id).where(visible_rooms(account_id))
    ).all())
