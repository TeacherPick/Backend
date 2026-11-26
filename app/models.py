from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, LargeBinary, SmallInteger,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

instant = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
long_text = Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
file_bytes = LargeBinary().with_variant(mysql.MEDIUMBLOB(), "mysql")
digest = LargeBinary(32).with_variant(mysql.BINARY(32), "mysql")
current_time = text("CURRENT_TIMESTAMP(6)")


class Created:
    created_at: Mapped[datetime] = mapped_column(instant, server_default=current_time)


class Account(Created, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("role IN ('teacher', 'instructor', 'admin')", name="role"),
        UniqueConstraint("username"),
        UniqueConstraint("email"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(254))
    name: Mapped[str | None] = mapped_column(String(100))
    organization: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    deleted_at: Mapped[datetime | None] = mapped_column(instant)


class InstructorProfile(Base):
    __tablename__ = "instructor_profiles"
    __table_args__ = (
        CheckConstraint("kind IN ('personal', 'company')", name="kind"),
        CheckConstraint("distance_km >= 0", name="distance"),
    )

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True,
    )
    photo_url: Mapped[str | None] = mapped_column(String(2048))
    specialty: Mapped[str | None] = mapped_column(String(255))
    experience: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), server_default=text("'personal'"))
    category: Mapped[str | None] = mapped_column(String(80))
    skills: Mapped[str | None] = mapped_column(String(500))
    audience: Mapped[str | None] = mapped_column(String(500))
    distance_km: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(instant, server_default=current_time)


class LoginSession(Created, Base):
    __tablename__ = "login_sessions"
    __table_args__ = (Index("ix_login_sessions_expires_at", "expires_at"),)

    token_hash: Mapped[bytes] = mapped_column(digest, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(instant)


class AdminLoginAttempt(Base):
    __tablename__ = "admin_login_attempts"
    __table_args__ = (Index("ix_admin_login_attempts_window_started_at", "window_started_at"),)

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    window_started_at: Mapped[datetime] = mapped_column(instant)
    blocked_until: Mapped[datetime | None] = mapped_column(instant)


class PasswordReset(Created, Base):
    __tablename__ = "password_resets"

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True,
    )
    nonce: Mapped[bytes] = mapped_column(digest)
    code_hash: Mapped[bytes | None] = mapped_column(digest)
    ticket_hash: Mapped[bytes | None] = mapped_column(digest)
    failures: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(instant)


class Post(Created, Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("view_count >= 0", name="views"),
        CheckConstraint("duration_minutes IS NULL OR duration_minutes > 0", name="duration"),
        CheckConstraint("distance_km >= 0", name="distance"),
        CheckConstraint("price >= 0", name="price"),
        Index("ix_posts_created", "created_at", "id"),
        Index("ix_posts_view_order", "view_count", "created_at", "id"),
        Index("ix_posts_author_created", "author_id", "created_at", "id"),
        Index("ix_posts_category_created", "category", "created_at", "id"),
        Index("ix_posts_audience_created", "audience", "created_at", "id"),
        Index("ix_posts_region_created", "region", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(long_text)
    category: Mapped[str] = mapped_column(String(80))
    audience: Mapped[str] = mapped_column(String(80))
    scale: Mapped[str] = mapped_column(String(80))
    skills: Mapped[str | None] = mapped_column(String(500))
    tech_stack: Mapped[str | None] = mapped_column(String(500))
    region: Mapped[str | None] = mapped_column(String(100))
    availability: Mapped[str | None] = mapped_column(String(500))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    distance_km: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[int | None] = mapped_column(Integer)
    additional_info: Mapped[str | None] = mapped_column(Text)
    view_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(instant, server_default=current_time)


class PostDeletion(Base):
    __tablename__ = "post_deletions"

    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    deleted_at: Mapped[datetime] = mapped_column(instant, server_default=current_time)


class AttachmentColumns:
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(file_bytes, deferred=True)


class PostAttachment(AttachmentColumns, Created, Base):
    __tablename__ = "post_attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), index=True,
    )


class Comment(Created, Base):
    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint("post_id", "id"),
        ForeignKeyConstraint(
            ("post_id", "parent_id"), ("comments.post_id", "comments.id"),
            name="fk_comments_parent_same_post", ondelete="CASCADE",
        ),
        Index("ix_comments_post_created", "post_id", "created_at", "id"),
        Index("ix_comments_author_created", "author_id", "created_at", "id"),
        Index("ix_comments_post_parent", "post_id", "parent_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    parent_id: Mapped[int | None] = mapped_column(BigInteger)
    body: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(instant)


class Reaction(Base):
    __tablename__ = "reactions"
    __table_args__ = (
        CheckConstraint("value IN (-1, 1)", name="value"),
        Index("ix_reactions_post_value", "post_id", "value"),
    )

    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True,
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True, index=True,
    )
    value: Mapped[int] = mapped_column(SmallInteger)


class ReactionChange(Base):
    __tablename__ = "reaction_changes"

    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True,
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True, index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(instant)


class Review(Created, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("post_id", "author_id"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating"),
        Index("ix_reviews_post_created", "post_id", "created_at", "id"),
        Index("ix_reviews_post_rating", "post_id", "rating", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), index=True)
    rating: Mapped[int] = mapped_column(SmallInteger)
    body: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(instant, server_default=current_time)


class ActivityLog(Created, Base):
    __tablename__ = "activity_logs"
    __table_args__ = (Index("ix_activity_logs_created", "created_at", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    resource: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[int] = mapped_column(BigInteger)


class Room(Created, Base):
    __tablename__ = "dm_rooms"
    __table_args__ = (
        UniqueConstraint("low_id", "high_id"),
        CheckConstraint("low_id < high_id", name="participant_order"),
        Index("ix_dm_rooms_low_active", "low_id", "low_active", "last_message_id"),
        Index("ix_dm_rooms_high_active", "high_id", "high_active", "last_message_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    low_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    high_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"))
    low_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))
    high_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))
    low_read_id: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    high_read_id: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    low_hidden_through: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    high_hidden_through: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    last_message_id: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))


class Message(Created, Base):
    __tablename__ = "dm_messages"
    __table_args__ = (
        UniqueConstraint("room_id", "sender_id", "client_id"),
        Index("ix_dm_messages_room_order", "room_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    room_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dm_rooms.id", ondelete="CASCADE"),
    )
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), index=True)
    client_id: Mapped[str] = mapped_column(String(36))
    body: Mapped[str | None] = mapped_column(Text)


class MessageAttachment(AttachmentColumns, Base):
    __tablename__ = "dm_attachments"

    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dm_messages.id", ondelete="CASCADE"), primary_key=True,
    )
