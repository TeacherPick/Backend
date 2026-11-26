from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.common import (
    FILE_RESPONSES, FilterText, Id, PageNumber, PageSize, ReviewSort, SearchText,
    parse_post, post_request_schema,
)
from app.dependencies import Db, OptionalPrincipal, User
from app.models import Review
from app.repositories.content import instructor_page, post_page, review_page
from app.schemas import (
    CommentEdit, CommentInput, CommentList, CommentRead, InstructorKind, InstructorRead, InstructorSummary,
    Page, PostInput, PostPatch, PostRead, PostSummary, ReactionInput, ReactionRead, ReviewInput,
    ReviewList, ReviewPatch, ReviewRead,
)
from app.services import content
from app.services.files import FileData, download

router = APIRouter(prefix="/posts", tags=["게시물"])
instructors = APIRouter(prefix="/instructors", tags=["강사"])
my_content = APIRouter(prefix="/me", tags=["내 활동"])
MaxDistance = Annotated[int | None, Query(ge=0, le=100000)]
MaxPrice = Annotated[int | None, Query(ge=0, le=2147483647)]


async def create_data(request: Request, principal: User) -> tuple[PostInput, list[FileData]]:
    content.require_instructor(principal.account)
    return await parse_post(request, PostInput)


async def update_data(request: Request, _principal: User) -> tuple[PostPatch, list[FileData]]:
    return await parse_post(request, PostPatch)


@router.get("")
def list_posts(
    db: Db, page: PageNumber = 1, size: PageSize = 20, q: SearchText = None,
    sort: Literal["latest", "views", "rating", "comments"] = "latest", category: FilterText = None,
    audience: FilterText = None, region: FilterText = None, max_distance: MaxDistance = None,
    max_price: MaxPrice = None,
) -> Page[PostSummary]:
    return post_page(db, page, size, q=q, sort=sort, category=category, audience=audience, region=region,
                     max_distance=max_distance, max_price=max_price)


@my_content.get("/posts")
def my_posts(db: Db, principal: User, page: PageNumber = 1, size: PageSize = 20) -> Page[PostSummary]:
    return post_page(db, page, size, author_id=principal.account.id)


@my_content.get("/reviews")
def my_reviews(db: Db, principal: User, page: PageNumber = 1, size: PageSize = 20, sort: ReviewSort = "latest") -> ReviewList:
    return review_page(db, [Review.author_id == principal.account.id], page, size, sort)


@router.post("", status_code=201, openapi_extra=post_request_schema(PostInput))
def create_post(
    db: Db, principal: User, payload: Annotated[tuple[PostInput, list[FileData]], Depends(create_data)],
) -> PostRead:
    data, files = payload
    return content.create_post(db, principal.account, data, files)


@router.get("/{post_id}")
def get_post(post_id: Id, db: Db) -> PostRead:
    return content.read_post(db, post_id)


@router.patch("/{post_id}", openapi_extra=post_request_schema(PostPatch))
def edit_post(
    post_id: Id, db: Db, principal: User,
    payload: Annotated[tuple[PostPatch, list[FileData]], Depends(update_data)],
) -> PostRead:
    data, files = payload
    return content.edit_post(db, principal.account, post_id, data, files)


@router.delete("/{post_id}", status_code=204)
def delete_post(post_id: Id, db: Db, principal: User) -> None:
    content.delete_post(db, principal.account, post_id)


@router.get("/{post_id}/attachments/{attachment_id}", response_class=Response, responses=FILE_RESPONSES)
def post_attachment(post_id: Id, attachment_id: Id, db: Db) -> Response:
    return download(content.get_post_attachment(db, post_id, attachment_id))


@router.get("/{post_id}/comments", tags=["댓글"])
def list_comments(post_id: Id, db: Db) -> CommentList:
    return content.list_comments(db, post_id)


@router.post("/{post_id}/comments", status_code=201, tags=["댓글"])
def create_comment(post_id: Id, data: CommentInput, db: Db, principal: User) -> CommentRead:
    return content.create_comment(db, post_id, principal.account, data)


@router.delete("/{post_id}/comments/{comment_id}", status_code=204, tags=["댓글"])
def delete_comment(post_id: Id, comment_id: Id, db: Db, principal: User) -> None:
    content.delete_comment(db, post_id, principal.account, comment_id)


@router.patch("/{post_id}/comments/{comment_id}", tags=["댓글"])
def edit_comment(post_id: Id, comment_id: Id, data: CommentEdit, db: Db, principal: User) -> CommentRead:
    return content.edit_comment(db, post_id, principal.account, comment_id, data)


@router.get("/{post_id}/reaction", tags=["추천"])
def get_reaction(post_id: Id, db: Db, principal: OptionalPrincipal) -> ReactionRead:
    return content.reaction_summary(db, post_id, principal.account.id if principal else None)


@router.post("/{post_id}/reaction", tags=["추천"])
def change_reaction(post_id: Id, data: ReactionInput, db: Db, principal: User) -> ReactionRead:
    return content.change_reaction(db, post_id, principal.account, data.value)


@router.get("/{post_id}/reviews", tags=["리뷰"])
def list_reviews(
    post_id: Id, db: Db, page: PageNumber = 1, size: PageSize = 20, sort: ReviewSort = "latest",
) -> ReviewList:
    return content.list_reviews(db, post_id, page, size, sort)


@router.post("/{post_id}/reviews", status_code=201, tags=["리뷰"])
def create_review(post_id: Id, data: ReviewInput, db: Db, principal: User) -> ReviewRead:
    return content.create_review(db, post_id, principal.account, data)


@router.patch("/{post_id}/reviews/{review_id}", tags=["리뷰"])
def edit_review(post_id: Id, review_id: Id, data: ReviewPatch, db: Db, principal: User) -> ReviewRead:
    return content.edit_review(db, post_id, review_id, principal.account, data)


@router.delete("/{post_id}/reviews/{review_id}", status_code=204, tags=["리뷰"])
def delete_review(post_id: Id, review_id: Id, db: Db, principal: User) -> None:
    content.delete_review(db, post_id, review_id, principal.account)


@instructors.get("")
def list_instructors(
    db: Db, page: PageNumber = 1, size: PageSize = 20, q: SearchText = None,
    category: FilterText = None, kind: InstructorKind | None = None,
    max_distance: MaxDistance = None, max_price: MaxPrice = None,
) -> Page[InstructorSummary]:
    return instructor_page(db, page, size, q=q, category=category, kind=kind,
                           max_distance=max_distance, max_price=max_price)


@instructors.get("/{instructor_id}")
def get_instructor(instructor_id: Id, db: Db, page: PageNumber = 1, size: PageSize = 20) -> InstructorRead:
    return content.get_instructor(db, instructor_id, page, size)


@instructors.get("/{instructor_id}/reviews")
def instructor_reviews(
    instructor_id: Id, db: Db, page: PageNumber = 1, size: PageSize = 20, sort: ReviewSort = "latest",
) -> ReviewList:
    return content.instructor_reviews(db, instructor_id, page, size, sort)
