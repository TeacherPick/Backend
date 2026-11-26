from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import AppError, Settings, token_digest
from app.db import get_db
from app.models import Account
from app.repositories.accounts import session_account
from app.services.auth import login_required

Db = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    account: Account
    digest: bytes


def authenticate(db: Session, token: str) -> Principal:
    if len(token) != 43 or not token.isascii():
        raise login_required()
    digest = token_digest(token)
    account = session_account(db, digest)
    if account is None:
        raise login_required()
    return Principal(account, digest)


def optional_principal(
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal | None:
    return authenticate(db, credentials.credentials) if credentials else None


OptionalPrincipal = Annotated[Principal | None, Depends(optional_principal)]


def require_user(principal: OptionalPrincipal) -> Principal:
    if principal is None:
        raise login_required()
    if principal.account.role == "admin":
        raise AppError(403, "user_required", "교사 또는 강사 계정이 필요합니다.")
    return principal


def require_admin(principal: OptionalPrincipal) -> Principal:
    if principal is None:
        raise login_required()
    if principal.account.role != "admin":
        raise AppError(403, "admin_required", "관리자 권한이 필요합니다.")
    return principal


def settings_for(request: Request) -> Settings:
    return request.app.state.settings


User = Annotated[Principal, Depends(require_user)]
Admin = Annotated[Principal, Depends(require_admin)]
AppSettings = Annotated[Settings, Depends(settings_for)]
