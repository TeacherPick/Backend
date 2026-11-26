from dataclasses import asdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from app.core import AppError, now_utc
from app.models import (
    Account, Comment, InstructorProfile, Post, PostAttachment, PostDeletion,
    Reaction, ReactionChange, Review,
)
from app.repositories.accounts import add_activity, lock_active_account
from app.repositories.content import (
    author, comment_rows, get_post, instructor_summary, post_aggregates, post_page, post_summary,
    review_page, review_read, review_stats,
)
from app.schemas import (
    CommentEdit, CommentInput, CommentList, CommentRead, InstructorRead, PostInput, PostPatch, PostRead,
    ReactionRead, ReviewInput, ReviewList, ReviewPatch, ReviewRead,
)
from app.services.files import MAX_POST_FILES, FileData
from app.services.auth import login_required


def _attachments(db: Session, post_id: int) -> list[PostAttachment]:
    return list(db.scalars(
        select(PostAttachment).where(PostAttachment.post_id == post_id).order_by(PostAttachment.id)
    ))


def _post_read(db: Session, post: Post, name: str | None) -> PostRead:
    organization, kind, comments, reviews, rating = db.execute(
        select(Account.organization, InstructorProfile.kind, *post_aggregates()).select_from(Post)
        .join(Account, Account.id == Post.author_id)
        .outerjoin(InstructorProfile, InstructorProfile.account_id == Post.author_id).where(Post.id == post.id)
    ).one()
    return PostRead(
        **post_summary(post, name, organization, kind, comments, reviews, rating).model_dump(),
        body=post.body, skills=post.skills, tech_stack=post.tech_stack,
        duration_minutes=post.duration_minutes, additional_info=post.additional_info,
        updated_at=post.updated_at, attachments=_attachments(db, post.id),
    )


def require_instructor(account: Account) -> None:
    if account.role != "instructor":
        raise AppError(403, "instructor_required", "강사 계정만 게시물을 작성할 수 있습니다.")


def _require_active(db: Session, account_id: int) -> None:
    if lock_active_account(db, account_id) is None:
        raise login_required()


def create_post(db: Session, account: Account, data: PostInput, files: list[FileData]) -> PostRead:
    require_instructor(account)
    _require_active(db, account.id)
    post = Post(author_id=account.id, **data.model_dump())
    db.add(post)
    db.flush()
    db.add_all(PostAttachment(post_id=post.id, **asdict(file)) for file in files)
    add_activity(db, account.id, "create", "post", post.id)
    db.flush()
    result = _post_read(db, post, account.name)
    db.commit()
    return result


def read_post(db: Session, post_id: int) -> PostRead:
    post = get_post(db, post_id, lock=True)
    post.view_count += 1
    name = db.scalar(select(Account.name).where(Account.id == post.author_id))
    result = _post_read(db, post, name)
    db.commit()
    return result


def edit_post(
    db: Session, account: Account, post_id: int, data: PostPatch, files: list[FileData],
) -> PostRead:
    _require_active(db, account.id)
    post = get_post(db, post_id, lock=True)
    if post.author_id != account.id:
        raise AppError(403, "post_edit_forbidden", "수정 권한이 없습니다.")
    updates = data.model_dump(exclude_unset=True, exclude={"remove_attachment_ids"})
    removals = set(data.remove_attachment_ids)
    if not updates and not removals and not files:
        raise AppError(422, "post_edit_empty", "수정할 내용을 입력해주세요.")
    existing = {file.id: file for file in _attachments(db, post.id)}
    if not removals <= existing.keys():
        raise AppError(404, "attachment_not_found", "존재하지 않는 첨부파일입니다.")
    if len(existing) - len(removals) + len(files) > MAX_POST_FILES:
        raise AppError(422, "too_many_files", "게시물당 최대 5개까지 첨부할 수 있습니다.")
    for field, value in updates.items():
        setattr(post, field, value)
    for file_id in removals:
        db.delete(existing[file_id])
    db.add_all(PostAttachment(post_id=post.id, **asdict(file)) for file in files)
    post.updated_at = now_utc()
    add_activity(db, account.id, "update", "post", post.id)
    db.flush()
    result = _post_read(db, post, account.name)
    db.commit()
    return result


def delete_post(db: Session, account: Account, post_id: int) -> None:
    _require_active(db, account.id)
    post = get_post(db, post_id, lock=True)
    if account.role != "admin" and post.author_id != account.id:
        raise AppError(403, "post_delete_forbidden", "삭제 권한이 없습니다.")
    add_activity(db, account.id, "delete", "post", post.id)
    db.add(PostDeletion(post_id=post.id))
    db.delete(post)
    db.commit()


def get_post_attachment(db: Session, post_id: int, attachment_id: int) -> PostAttachment:
    get_post(db, post_id)
    attachment = db.scalar(select(PostAttachment).where(
        PostAttachment.id == attachment_id, PostAttachment.post_id == post_id,
    ).options(undefer(PostAttachment.data)))
    if attachment is None:
        raise AppError(404, "attachment_not_found", "존재하지 않는 첨부파일입니다.")
    return attachment


def _comment_read(comment: Comment, name: str | None) -> CommentRead:
    deleted = comment.deleted_at is not None
    return CommentRead(
        id=comment.id, parent_id=comment.parent_id,
        author=None if deleted else author(comment.author_id, name),
        body="삭제된 댓글입니다." if deleted else comment.body,
        deleted=deleted, created_at=comment.created_at,
    )


def list_comments(db: Session, post_id: int) -> CommentList:
    get_post(db, post_id)
    rows = comment_rows(db, post_id)
    roots = {}
    replies = []
    total = 0
    for comment, name in rows:
        if comment.parent_id is None:
            roots[comment.id] = _comment_read(comment, name)
        elif comment.deleted_at is None:
            replies.append(_comment_read(comment, name))
        if comment.deleted_at is None:
            total += 1
    for reply in replies:
        roots[reply.parent_id].replies.append(reply)
    return CommentList(
        items=[root for root in roots.values() if not root.deleted or root.replies], total=total,
    )


def _get_comment(db: Session, post_id: int, comment_id: int) -> Comment:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.post_id != post_id:
        raise AppError(404, "comment_not_found", "존재하지 않는 댓글입니다.")
    if comment.deleted_at is not None:
        raise AppError(410, "comment_deleted", "삭제된 댓글입니다.")
    return comment


def create_comment(db: Session, post_id: int, account: Account, data: CommentInput) -> CommentRead:
    _require_active(db, account.id)
    get_post(db, post_id, lock=True)
    if data.parent_id is not None:
        parent = _get_comment(db, post_id, data.parent_id)
        if parent.parent_id is not None:
            raise AppError(422, "reply_depth_exceeded", "답글에는 답글을 작성할 수 없습니다.")
    comment = Comment(post_id=post_id, author_id=account.id, body=data.body, parent_id=data.parent_id)
    db.add(comment)
    db.flush()
    add_activity(db, account.id, "create", "comment", comment.id)
    result = _comment_read(comment, account.name)
    db.commit()
    return result


def delete_comment(db: Session, post_id: int, account: Account, comment_id: int) -> None:
    _require_active(db, account.id)
    get_post(db, post_id, lock=True)
    comment = _get_comment(db, post_id, comment_id)
    if comment.author_id != account.id:
        raise AppError(403, "comment_delete_forbidden", "삭제 권한이 없습니다.")
    comment.deleted_at = now_utc()
    comment.body = None
    add_activity(db, account.id, "delete", "comment", comment.id)
    db.commit()


def edit_comment(db: Session, post_id: int, account: Account, comment_id: int, data: CommentEdit) -> CommentRead:
    _require_active(db, account.id)
    get_post(db, post_id, lock=True)
    comment = _get_comment(db, post_id, comment_id)
    if comment.author_id != account.id:
        raise AppError(403, "comment_edit_forbidden", "수정 권한이 없습니다.")
    comment.body = data.body
    add_activity(db, account.id, "update", "comment", comment.id)
    result = _comment_read(comment, account.name)
    db.commit()
    return result


def reaction_summary(db: Session, post_id: int, account_id: int | None) -> ReactionRead:
    get_post(db, post_id)
    counts = dict(db.execute(
        select(Reaction.value, func.count()).where(Reaction.post_id == post_id).group_by(Reaction.value)
    ).all())
    current = db.get(Reaction, (post_id, account_id)) if account_id is not None else None
    return ReactionRead(likes=counts.get(1, 0), dislikes=counts.get(-1, 0), current=current.value if current else None)


def change_reaction(db: Session, post_id: int, account: Account, value: int) -> ReactionRead:
    _require_active(db, account.id)
    post = get_post(db, post_id, lock=True)
    if post.author_id == account.id:
        raise AppError(403, "own_post_reaction", "본인의 게시물에는 추천할 수 없습니다.")
    key = (post_id, account.id)
    change = db.get(ReactionChange, key)
    now = now_utc()
    if change is not None and now < change.changed_at + timedelta(seconds=1):
        raise AppError(429, "reaction_too_fast", "잠시 후 다시 시도해주세요.", {"Retry-After": "1"})
    if change is None:
        db.add(ReactionChange(post_id=post_id, account_id=account.id, changed_at=now))
    else:
        change.changed_at = now
    reaction = db.get(Reaction, key)
    if reaction is None:
        db.add(Reaction(post_id=post_id, account_id=account.id, value=value))
    elif reaction.value == value:
        db.delete(reaction)
    else:
        reaction.value = value
    db.flush()
    result = reaction_summary(db, post_id, account.id)
    db.commit()
    return result


def list_reviews(db: Session, post_id: int, page: int, size: int, sort: str) -> ReviewList:
    get_post(db, post_id)
    return review_page(db, [Review.post_id == post_id], page, size, sort)


def create_review(db: Session, post_id: int, account: Account, data: ReviewInput) -> ReviewRead:
    _require_active(db, account.id)
    get_post(db, post_id, lock=True)
    exists = db.scalar(select(Review.id).where(Review.post_id == post_id, Review.author_id == account.id))
    if exists is not None:
        raise AppError(409, "review_exists", "이미 리뷰를 작성했습니다.")
    review = Review(post_id=post_id, author_id=account.id, **data.model_dump())
    db.add(review)
    db.flush()
    add_activity(db, account.id, "create", "review", review.id)
    result = review_read(review, account.name)
    db.commit()
    return result


def _owned_review(db: Session, post_id: int, review_id: int, account: Account) -> Review:
    _require_active(db, account.id)
    get_post(db, post_id, lock=True)
    review = db.get(Review, review_id)
    if review is None or review.post_id != post_id:
        raise AppError(404, "review_not_found", "존재하지 않는 리뷰입니다.")
    if review.author_id != account.id:
        raise AppError(403, "review_forbidden", "권한이 없습니다.")
    return review


def edit_review(db: Session, post_id: int, review_id: int, account: Account, data: ReviewPatch) -> ReviewRead:
    review = _owned_review(db, post_id, review_id, account)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    review.updated_at = now_utc()
    add_activity(db, account.id, "update", "review", review.id)
    result = review_read(review, account.name)
    db.commit()
    return result


def delete_review(db: Session, post_id: int, review_id: int, account: Account) -> None:
    review = _owned_review(db, post_id, review_id, account)
    add_activity(db, account.id, "delete", "review", review.id)
    db.delete(review)
    db.commit()


def _instructor(db: Session, account_id: int) -> Account:
    instructor = db.get(Account, account_id)
    if instructor is None or instructor.role != "instructor":
        raise AppError(404, "instructor_not_found", "존재하지 않는 사용자입니다.")
    if instructor.deleted_at:
        raise AppError(410, "account_deleted", "탈퇴한 사용자입니다.")
    return instructor


def get_instructor(db: Session, account_id: int, page: int, size: int) -> InstructorRead:
    instructor = _instructor(db, account_id)
    profile = db.get(InstructorProfile, account_id)
    programs = post_page(db, page, size, author_id=account_id)
    count, average = review_stats(db, [Post.author_id == account_id])
    return InstructorRead(
        **instructor_summary(instructor, profile).model_dump(), programs=programs,
        average_rating=average, review_count=count,
    )


def instructor_reviews(db: Session, account_id: int, page: int, size: int, sort: str) -> ReviewList:
    _instructor(db, account_id)
    return review_page(db, [Post.author_id == account_id], page, size, sort)
