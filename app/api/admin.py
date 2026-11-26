from fastapi import APIRouter
from sqlalchemy import or_

from app.api.common import Id, PageNumber, PageSize, SearchText
from app.dependencies import Admin, Db
from app.models import Account, ActivityLog, Comment
from app.repositories.content import page_of, post_page
from app.schemas import AccountCommentRead, AccountRead, ActivityRead, Page, PostSummary
from app.services import admin, content

router = APIRouter(prefix="/admin", tags=["관리자"])


@router.get("/posts")
def list_posts(db: Db, _admin: Admin, page: PageNumber = 1, size: PageSize = 20, q: SearchText = None) -> Page[PostSummary]:
    return post_page(db, page, size, q=q)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(db: Db, principal: Admin, post_id: Id) -> None:
    content.delete_post(db, principal.account, post_id)


@router.get("/activity-logs")
def activity(db: Db, _admin: Admin, page: PageNumber = 1, size: PageSize = 20) -> Page[ActivityRead]:
    return page_of(db, ActivityLog, ActivityRead, [], [ActivityLog.created_at.desc(), ActivityLog.id.desc()], page, size)


@router.get("/accounts")
def accounts(db: Db, _admin: Admin, page: PageNumber = 1, size: PageSize = 20, q: SearchText = None) -> Page[AccountRead]:
    filters = [Account.deleted_at.is_(None), Account.role != "admin"]
    if q:
        filters.append(or_(Account.name.contains(q, autoescape=True), Account.email.contains(q, autoescape=True)))
    return page_of(
        db, Account, AccountRead, filters,
        [Account.created_at.desc(), Account.id.desc()], page, size,
    )


@router.get("/accounts/{account_id}")
def account(db: Db, _admin: Admin, account_id: Id) -> AccountRead:
    return AccountRead.model_validate(admin.get_member(db, account_id))


@router.get("/accounts/{account_id}/posts")
def account_posts(
    db: Db, _admin: Admin, account_id: Id, page: PageNumber = 1, size: PageSize = 20,
) -> Page[PostSummary]:
    admin.get_member(db, account_id)
    return post_page(db, page, size, author_id=account_id)


@router.get("/accounts/{account_id}/comments")
def account_comments(
    db: Db, _admin: Admin, account_id: Id, page: PageNumber = 1, size: PageSize = 20,
) -> Page[AccountCommentRead]:
    admin.get_member(db, account_id)
    return page_of(
        db, Comment, AccountCommentRead, [Comment.author_id == account_id, Comment.deleted_at.is_(None)],
        [Comment.created_at.desc(), Comment.id.desc()], page, size,
    )


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(db: Db, principal: Admin, account_id: Id) -> None:
    admin.delete_member(db, principal.account.id, account_id)
