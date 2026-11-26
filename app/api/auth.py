from fastapi import APIRouter

from app.dependencies import Admin, AppSettings, Db, User
from app.schemas import AccountPatch, AccountRead, Login, Register, ResetConfirm, ResetRequest, ResetTicket, ResetVerify, TokenRead
from app.services import auth

router = APIRouter(prefix="/auth", tags=["인증"])
admin_router = APIRouter(prefix="/admin/auth", tags=["관리자 인증"])


@router.post("/register", status_code=201)
def register(data: Register, db: Db) -> AccountRead:
    return auth.register(db, data)


@router.post("/login")
def login(data: Login, db: Db, settings: AppSettings) -> TokenRead:
    return auth.login(db, data, settings, admin=False)


@router.post("/logout", status_code=204)
def logout(db: Db, principal: User) -> None:
    auth.logout(db, principal.digest)


@router.get("/me")
def current_account(principal: User) -> AccountRead:
    return AccountRead.model_validate(principal.account)


@router.patch("/me")
def update_account(data: AccountPatch, db: Db, principal: User) -> AccountRead:
    return auth.update_account(db, principal.account.id, data)


@router.post("/password-reset/request", status_code=202)
def request_reset(data: ResetRequest, db: Db, settings: AppSettings) -> dict[str, str]:
    auth.request_reset(db, str(data.email), settings)
    return {"message": "가입한 이메일이면 인증번호가 전송됩니다."}


@router.post("/password-reset/verify")
def verify_reset(data: ResetVerify, db: Db, settings: AppSettings) -> ResetTicket:
    return ResetTicket(ticket=auth.verify_reset(db, data, settings))


@router.post("/password-reset/confirm", status_code=204)
def confirm_reset(data: ResetConfirm, db: Db) -> None:
    auth.confirm_reset(db, data)


@admin_router.post("/login")
def admin_login(data: Login, db: Db, settings: AppSettings) -> TokenRead:
    return auth.login(db, data, settings, admin=True)


@admin_router.post("/logout", status_code=204)
def admin_logout(db: Db, principal: Admin) -> None:
    auth.logout(db, principal.digest)


@admin_router.get("/me")
def current_admin(principal: Admin) -> AccountRead:
    return AccountRead.model_validate(principal.account)
