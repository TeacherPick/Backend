from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core import AppError, now_utc
from app.models import Account, InstructorProfile, PasswordReset, Reaction, ReactionChange
from app.repositories.accounts import add_activity, revoke_sessions


def get_member(db: Session, member_id: int, *, lock: bool = False) -> Account:
    account = db.get(Account, member_id, with_for_update=lock)
    if account is None or account.role == "admin":
        raise AppError(404, "account_not_found", "존재하지 않는 계정입니다.")
    if account.deleted_at is not None:
        raise AppError(410, "account_deleted", "탈퇴한 사용자입니다.")
    return account


def delete_member(db: Session, admin_id: int, member_id: int) -> None:
    account = get_member(db, member_id, lock=True)
    account.username = None
    account.name = None
    account.email = None
    account.organization = None
    account.phone = None
    account.password_hash = None
    account.deleted_at = now_utc()
    revoke_sessions(db, member_id)
    db.execute(delete(PasswordReset).where(PasswordReset.account_id == member_id))
    db.execute(delete(InstructorProfile).where(InstructorProfile.account_id == member_id))
    db.execute(delete(Reaction).where(Reaction.account_id == member_id))
    db.execute(delete(ReactionChange).where(ReactionChange.account_id == member_id))
    add_activity(db, admin_id, "delete", "account", member_id)
    db.commit()
