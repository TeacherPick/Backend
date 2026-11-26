from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, load_only

from app.core import AppError
from app.models import Account, Comment, InstructorProfile, Post, PostDeletion, Review
from app.schemas import Author, InstructorSummary, Page, PostSummary, Record, ReviewList, ReviewRead

ReadSchema = TypeVar("ReadSchema", bound=Record)


def get_post(db: Session, post_id: int, *, lock: bool = False) -> Post:
    post = db.get(Post, post_id, with_for_update=lock)
    if post is not None:
        return post
    if db.get(PostDeletion, post_id):
        raise AppError(410, "post_deleted", "삭제된 게시물입니다.")
    raise AppError(404, "post_not_found", "존재하지 않는 게시물입니다.")


def author(id_: int, name: str | None) -> Author:
    return Author(id=id_, name=name)


def page_of(
    db: Session, model, schema: type[ReadSchema], filters: Sequence, order: Sequence, page: int, size: int,
) -> Page[ReadSchema]:
    total = db.scalar(select(func.count()).select_from(model).where(*filters))
    rows = db.scalars(
        select(model).where(*filters).order_by(*order).offset((page - 1) * size).limit(size)
    ).all()
    return Page[schema](items=[schema.model_validate(row) for row in rows], total=total, page=page, size=size)


def post_page(
    db: Session, page: int, size: int, *, q: str | None = None, sort: str = "latest",
    category: str | None = None, audience: str | None = None, region: str | None = None,
    author_id: int | None = None, max_distance: int | None = None, max_price: int | None = None,
) -> Page[PostSummary]:
    filters = [
        field == value for field, value in (
            (Post.category, category), (Post.audience, audience), (Post.region, region),
            (Post.author_id, author_id),
        ) if value is not None
    ]
    if q:
        filters.append(or_(*(column.contains(q, autoescape=True) for column in (
            Post.title, Account.name, Post.category, Post.skills, Post.tech_stack, Post.body,
        ))))
    if max_distance is not None:
        filters.append(Post.distance_km <= max_distance)
    if max_price is not None:
        filters.append(Post.price <= max_price)
    comments, reviews, rating = post_aggregates()
    order = [Post.created_at.desc(), Post.id.desc()]
    sort_column = {"views": Post.view_count, "rating": rating, "comments": comments}.get(sort)
    if sort_column is not None:
        order.insert(0, sort_column.desc())
    base = (
        select(Post, Account.name, Account.organization, InstructorProfile.kind, comments, reviews, rating)
        .join(Account, Account.id == Post.author_id)
        .outerjoin(InstructorProfile, InstructorProfile.account_id == Post.author_id).where(*filters)
    )
    count = db.scalar(
        select(func.count()).select_from(Post).join(Account, Account.id == Post.author_id).where(*filters)
    )
    rows = db.execute(
        base.options(load_only(
            Post.author_id, Post.title, Post.category, Post.audience, Post.scale, Post.region,
            Post.view_count, Post.created_at, Post.body, Post.availability, Post.distance_km, Post.price,
        ))
        .order_by(*order).offset((page - 1) * size).limit(size)
    )
    return Page[PostSummary](
        items=[post_summary(*row) for row in rows], total=count, page=page, size=size,
    )


def post_aggregates():
    comments = (select(func.count()).select_from(Comment)
                .where(Comment.post_id == Post.id, Comment.deleted_at.is_(None)).correlate(Post).scalar_subquery())
    reviews = select(Review).where(Review.post_id == Post.id).correlate(Post)
    count = reviews.with_only_columns(func.count(), maintain_column_froms=True).scalar_subquery()
    rating = reviews.with_only_columns(func.avg(Review.rating)).scalar_subquery()
    return comments, count, rating


def post_summary(
    post: Post, name: str | None, organization: str | None, kind: str | None,
    comments: int, reviews: int, rating: float | None,
) -> PostSummary:
    return PostSummary(
        id=post.id, author=author(post.author_id, name), title=post.title,
        category=post.category, audience=post.audience, scale=post.scale, region=post.region,
        view_count=post.view_count, created_at=post.created_at, description=post.body[:300],
        availability=post.availability, distance_km=post.distance_km, price=post.price,
        instructor_kind=kind or "personal", instructor_organization=organization,
        comment_count=comments, review_count=reviews, average_rating=rating,
    )


def instructor_summary(account: Account, profile: InstructorProfile | None) -> InstructorSummary:
    fields = ("photo_url", "specialty", "experience", "bio", "category", "skills", "audience", "distance_km")
    return InstructorSummary(
        id=account.id, name=account.name, organization=account.organization,
        kind=profile.kind if profile else "personal",
        **{field: getattr(profile, field, None) for field in fields},
    )


def instructor_page(
    db: Session, page: int, size: int, *, q: str | None, category: str | None, kind: str | None,
    max_distance: int | None, max_price: int | None,
) -> Page[InstructorSummary]:
    filters = [Account.role == "instructor", Account.deleted_at.is_(None)]
    if q:
        filters.append(or_(*(column.contains(q, autoescape=True) for column in (
            Account.name, InstructorProfile.specialty, InstructorProfile.skills, InstructorProfile.bio,
        ))))
    if category:
        filters.append(or_(InstructorProfile.category == category, select(Post.id)
                          .where(Post.author_id == Account.id, Post.category == category).exists()))
    if kind:
        filters.append(func.coalesce(InstructorProfile.kind, "personal") == kind)
    if max_distance is not None:
        filters.append(InstructorProfile.distance_km <= max_distance)
    if max_price is not None:
        filters.append(select(Post.id).where(Post.author_id == Account.id, Post.price <= max_price).exists())
    query = select(Account, InstructorProfile).outerjoin(InstructorProfile).where(*filters)
    total = db.scalar(query.with_only_columns(func.count(), maintain_column_froms=True).order_by(None))
    rows = db.execute(query.order_by(Account.name, Account.id).offset((page - 1) * size).limit(size))
    return Page[InstructorSummary](items=[instructor_summary(*row) for row in rows], total=total, page=page, size=size)


def comment_rows(db: Session, post_id: int) -> Sequence:
    return db.execute(
        select(Comment, Account.name)
        .join(Account, Account.id == Comment.author_id)
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at, Comment.id)
    ).all()


def review_stats(db: Session, filters: Sequence) -> tuple[int, float | None]:
    count, average = db.execute(
        select(func.count(), func.avg(Review.rating)).select_from(Review)
        .join(Post, Post.id == Review.post_id).where(*filters)
    ).one()
    return count, float(average) if average is not None else None


def review_page(
    db: Session, filters: Sequence, page: int, size: int, sort: str,
) -> ReviewList:
    count, average = review_stats(db, filters)
    base: Select = (
        select(Review, Account.name, Post.title)
        .join(Post, Post.id == Review.post_id)
        .join(Account, Account.id == Review.author_id)
        .where(*filters)
    )
    order = [Review.created_at.desc(), Review.id.desc()]
    if sort == "rating":
        order.insert(0, Review.rating.desc())
    rows = db.execute(base.order_by(*order).offset((page - 1) * size).limit(size))
    return ReviewList(
        items=[review_read(*row) for row in rows],
        total=count, average_rating=average, page=page, size=size,
    )


def review_read(review: Review, name: str | None, post_title: str | None = None) -> ReviewRead:
    return ReviewRead(
        id=review.id, post_id=review.post_id, author=author(review.author_id, name), rating=review.rating,
        body=review.body, created_at=review.created_at, updated_at=review.updated_at, post_title=post_title,
    )
