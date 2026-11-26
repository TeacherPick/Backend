import math
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import AppError, Settings, code_digest, now_utc, password_hasher, password_matches, token_digest
from app.models import Account, AdminLoginAttempt, InstructorProfile, LoginSession, PasswordReset
from app.repositories.accounts import account_by_email, revoke_sessions
from app.schemas import AccountPatch, AccountRead, Login, Register, ResetConfirm, ResetVerify, TokenRead

ADMIN_WINDOW = timedelta(minutes=5)
RESET_LIFETIME = timedelta(minutes=10)


def login_required() -> AppError:
    return AppError(401, "authentication_required", "로그인이 필요합니다.", {"WWW-Authenticate": "Bearer"})


def register(db: Session, data: Register) -> AccountRead:
    account = Account(
        role=data.role,
        name=data.name,
        username=data.username,
        email=data.email.lower(),
        organization=data.organization,
        phone=data.phone,
        password_hash=password_hasher.hash(data.password.get_secret_value()),
    )
    db.add(account)
    try:
        if data.profile is not None:
            db.flush()
            db.add(InstructorProfile(account_id=account.id, **data.profile.model_dump(mode="json")))
        db.commit()
    except IntegrityError as exc:
        if exc.orig.args[0] != 1062:
            raise
        raise AppError(409, "account_exists", "이미 가입된 계정입니다.") from exc
    return AccountRead.model_validate(account)


def update_account(db: Session, account_id: int, data: AccountPatch) -> AccountRead:
    account = db.scalar(select(Account).where(Account.id == account_id).with_for_update()
                        .execution_options(populate_existing=True))
    if account is None or account.deleted_at is not None:
        raise login_required()
    email = data.email.lower()
    if email != account.email:
        if data.current_password is None or not password_matches(
            account.password_hash, data.current_password.get_secret_value(),
        ):
            raise AppError(403, "current_password_required", "이메일을 변경하려면 현재 비밀번호를 확인해주세요.")
        db.execute(delete(PasswordReset).where(PasswordReset.account_id == account.id))
        account.email = email
    account.name = data.name
    for field in ("organization", "phone"):
        if field in data.model_fields_set:
            setattr(account, field, getattr(data, field))
    try:
        db.commit()
    except IntegrityError as exc:
        if exc.orig.args[0] != 1062:
            raise
        raise AppError(409, "account_exists", "이미 사용 중인 이메일입니다.") from exc
    return AccountRead.model_validate(account)


def _admin_attempt(db: Session, username: str) -> AdminLoginAttempt:
    stmt = insert(AdminLoginAttempt).values(username=username, window_started_at=now_utc())
    db.execute(stmt.on_duplicate_key_update(username=stmt.inserted.username))
    attempt = db.get(AdminLoginAttempt, username, with_for_update=True)
    assert attempt is not None
    now = now_utc()
    if attempt.blocked_until and attempt.blocked_until > now:
        retry = math.ceil((attempt.blocked_until - now).total_seconds())
        raise AppError(429, "admin_login_limited", "5분 뒤 다시 시도해주세요.", {"Retry-After": str(retry)})
    if attempt.blocked_until or attempt.window_started_at + ADMIN_WINDOW <= now:
        attempt.failures = 0
        attempt.window_started_at = now
        attempt.blocked_until = None
    return attempt


def login(db: Session, data: Login, settings: Settings, *, admin: bool) -> TokenRead:
    attempt = _admin_attempt(db, data.username) if admin else None
    role_condition = Account.role == "admin" if admin else Account.role != "admin"
    account = db.scalar(
        select(Account)
        .where(Account.username == data.username, Account.deleted_at.is_(None), role_condition)
        .with_for_update()
    )
    valid = password_matches(account.password_hash if account else None, data.password.get_secret_value())
    if not valid or account is None:
        if attempt is not None:
            attempt.failures += 1
            if attempt.failures == 5:
                attempt.blocked_until = now_utc() + ADMIN_WINDOW
            db.commit()
        code = "account_not_found" if account is None else "invalid_password"
        message = "존재하지 않는 계정입니다." if account is None else "비밀번호가 올바르지 않습니다."
        raise AppError(401, code, message, {"WWW-Authenticate": "Bearer"})
    if attempt is not None:
        db.delete(attempt)
    if password_hasher.check_needs_rehash(account.password_hash):
        account.password_hash = password_hasher.hash(data.password.get_secret_value())
    token = secrets.token_urlsafe(32)
    expiry = now_utc() + timedelta(minutes=settings.session_minutes)
    db.add(LoginSession(token_hash=token_digest(token), account_id=account.id, expires_at=expiry))
    result = TokenRead(access_token=token, expires_at=expiry, account=AccountRead.model_validate(account))
    db.commit()
    return result


def logout(db: Session, digest: bytes) -> None:
    db.execute(delete(LoginSession).where(LoginSession.token_hash == digest))
    db.commit()


def _reset_pepper(settings: Settings) -> str:
    key = settings.reset_code_pepper.get_secret_value()
    if len(key) < 32 or not settings.smtp_host or not settings.smtp_sender:
        raise AppError(503, "password_reset_unavailable", "비밀번호 재설정을 현재 사용할 수 없습니다.")
    return key


def send_reset_email(settings: Settings, email: str, code: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_sender
    msg["To"] = email
    msg["Subject"] = "비밀번호 재설정 인증번호"
    msg.set_content(f"비밀번호 재설정 인증번호는 {code}입니다. 10분 이내에 입력해주세요.")
    context = ssl.create_default_context()
    if settings.smtp_security == "implicit":
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=8, context=context)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=8)
    with server:
        if settings.smtp_security == "starttls":
            server.starttls(context=context)
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        server.send_message(msg)


def request_reset(db: Session, email: str, settings: Settings) -> None:
    key = _reset_pepper(settings)
    account = account_by_email(db, email)
    if account is None:
        return
    challenge = db.get(PasswordReset, account.id)
    now = now_utc()
    if challenge is not None and challenge.created_at + timedelta(minutes=1) > now:
        return
    code = f"{secrets.randbelow(1_000_000):06d}"
    nonce = secrets.token_bytes(32)
    if challenge is None:
        challenge = PasswordReset(account_id=account.id)
        db.add(challenge)
    challenge.nonce = nonce
    challenge.code_hash = code_digest(key, nonce, code)
    challenge.ticket_hash = None
    challenge.failures = 0
    challenge.created_at = now
    challenge.expires_at = now + RESET_LIFETIME
    account_id, recipient = account.id, account.email
    db.commit()
    try:
        send_reset_email(settings, recipient, code)
    except (OSError, smtplib.SMTPException) as exc:
        db.execute(delete(PasswordReset).where(PasswordReset.account_id == account_id, PasswordReset.nonce == nonce))
        db.commit()
        raise AppError(503, "email_delivery_failed", "인증번호를 전송하지 못했습니다. 다시 시도해주세요.") from exc


def verify_reset(db: Session, data: ResetVerify, settings: Settings) -> str:
    key = _reset_pepper(settings)
    account = account_by_email(db, str(data.email))
    challenge = db.get(PasswordReset, account.id) if account else None
    if challenge is None or challenge.code_hash is None:
        raise AppError(400, "invalid_reset_code", "인증번호가 올바르지 않습니다.")
    now = now_utc()
    if challenge.expires_at <= now:
        raise AppError(410, "reset_code_expired", "인증번호가 만료되었습니다. 다시 요청해주세요.")
    if challenge.failures >= 5:
        raise AppError(429, "reset_attempts_exceeded", "인증번호를 다시 요청해주세요.")
    expected = code_digest(key, challenge.nonce, data.code.get_secret_value())
    if not secrets.compare_digest(expected, challenge.code_hash):
        challenge.failures += 1
        db.commit()
        raise AppError(400, "invalid_reset_code", "인증번호가 올바르지 않습니다.")
    ticket = secrets.token_urlsafe(32)
    challenge.code_hash = None
    challenge.ticket_hash = token_digest(ticket)
    challenge.expires_at = now + RESET_LIFETIME
    db.commit()
    return ticket


def confirm_reset(db: Session, data: ResetConfirm) -> None:
    account = account_by_email(db, str(data.email))
    challenge = db.get(PasswordReset, account.id) if account else None
    digest = token_digest(data.ticket.get_secret_value())
    if challenge is None or challenge.ticket_hash is None or not secrets.compare_digest(challenge.ticket_hash, digest):
        raise AppError(400, "invalid_reset_ticket", "비밀번호 재설정 인증이 필요합니다.")
    if challenge.expires_at <= now_utc():
        raise AppError(410, "reset_ticket_expired", "인증이 만료되었습니다. 다시 요청해주세요.")
    account.password_hash = password_hasher.hash(data.password.get_secret_value())
    db.delete(challenge)
    revoke_sessions(db, account.id)
    db.commit()
