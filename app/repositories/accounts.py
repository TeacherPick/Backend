from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import now_utc
from app.models import Account, ActivityLog, LoginSession


def session_account(db: Session, digest: bytes) -> Account | None:
    return db.scalar(
        select(Account)
        .join(LoginSession, LoginSession.account_id == Account.id)
        .where(
            LoginSession.token_hash == digest,
            LoginSession.expires_at > now_utc(),
            Account.deleted_at.is_(None),
        )
    )


def account_by_email(db: Session, email: str) -> Account | None:
    return db.scalar(
        select(Account)
        .where(Account.email == email.lower(), Account.role != "admin", Account.deleted_at.is_(None))
        .with_for_update()
    )


def lock_active_account(db: Session, account_id: int) -> Account | None:
    return db.scalar(
        select(Account).where(Account.id == account_id, Account.deleted_at.is_(None))
        .with_for_update(read=True).execution_options(populate_existing=True)
    )


def revoke_sessions(db: Session, account_id: int) -> None:
    db.execute(delete(LoginSession).where(LoginSession.account_id == account_id))


def add_activity(
    db: Session, actor_id: int, action: str, resource: str, resource_id: int,
) -> None:
    db.add(ActivityLog(actor_id=actor_id, action=action, resource=resource, resource_id=resource_id))
