from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import (
    AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, SecretStr,
    StringConstraints, UrlConstraints, field_serializer, field_validator, model_validator,
)

T = TypeVar("T")
Role = Literal["teacher", "instructor", "admin"]
Identifier = Annotated[int, Field(gt=0, le=9223372036854775807)]
Username = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-zA-Z0-9_.-]{3,64}$"),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]
LoginPassword = Annotated[SecretStr, Field(min_length=1, max_length=128)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PostBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30000)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ShortNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
LongNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
CommentBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Rating = Annotated[int, Field(strict=True, ge=1, le=5)]
InstructorKind = Literal["personal", "company"]
Distance = Annotated[int, Field(strict=True, ge=0, le=100000)]
Price = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()-]{4,30}[0-9]$")]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def encode_datetime(self, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.isoformat(timespec="microseconds") + "Z"
        return value


class Page(Record, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class Author(Record):
    id: int
    name: str | None


class AccountRead(Record):
    id: int
    username: str
    name: str
    email: str
    role: Role
    created_at: datetime
    organization: str | None = None
    phone: str | None = None


class AccountFields(Input):
    name: Name
    email: EmailStr
    organization: Name | None = None
    phone: Phone | None = None


class AccountPatch(AccountFields):
    current_password: LoginPassword | None = None


class Login(Input):
    username: Username
    password: LoginPassword


class PasswordPair(Input):
    password: Password
    password_confirmation: Password

    @model_validator(mode="after")
    def match_passwords(self):
        if self.password != self.password_confirmation:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return self


class TokenRead(Record):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    account: AccountRead


class ResetRequest(Input):
    email: EmailStr


class ResetVerify(ResetRequest):
    code: Annotated[SecretStr, Field(min_length=6, max_length=6)]

    @field_validator("code")
    @classmethod
    def validate_code(cls, code: SecretStr) -> SecretStr:
        if not code.get_secret_value().isascii() or not code.get_secret_value().isdigit():
            raise ValueError("인증번호는 숫자 6자리입니다.")
        return code


class ResetTicket(Record):
    ticket: str


class ResetConfirm(PasswordPair):
    email: EmailStr
    ticket: Annotated[SecretStr, Field(min_length=43, max_length=43)]


class ProfileData(Input):
    photo_url: Annotated[AnyHttpUrl, UrlConstraints(max_length=2048)] | None = None
    specialty: Annotated[str, StringConstraints(max_length=255)] | None = None
    experience: LongNote | None = None
    bio: LongNote | None = None
    kind: InstructorKind = "personal"
    category: Label | None = None
    skills: ShortNote | None = None
    audience: ShortNote | None = None
    distance_km: Distance | None = None


class Register(PasswordPair, AccountFields):
    username: Username
    role: Literal["teacher", "instructor"]
    profile: ProfileData | None = None

    @model_validator(mode="after")
    def validate_profile_role(self):
        if self.role != "instructor" and self.profile is not None:
            raise ValueError("강사 계정만 강사 프로필을 등록할 수 있습니다.")
        return self


class PostInput(Input):
    title: Title
    body: PostBody
    category: Label
    audience: Label
    scale: Label
    skills: ShortNote | None = None
    tech_stack: ShortNote | None = None
    region: Name | None = None
    availability: ShortNote | None = None
    duration_minutes: Annotated[int, Field(strict=True, gt=0, le=2147483647)] | None = None
    distance_km: Distance | None = None
    price: Price | None = None
    additional_info: LongNote | None = None


class PostPatch(Input):
    title: Title | None = None
    body: PostBody | None = None
    category: Label | None = None
    audience: Label | None = None
    scale: Label | None = None
    skills: ShortNote | None = None
    tech_stack: ShortNote | None = None
    region: Name | None = None
    availability: ShortNote | None = None
    duration_minutes: Annotated[int, Field(strict=True, gt=0, le=2147483647)] | None = None
    distance_km: Distance | None = None
    price: Price | None = None
    additional_info: LongNote | None = None
    remove_attachment_ids: Annotated[list[Identifier], Field(max_length=5)] = []

    @field_validator("title", "body", "category", "audience", "scale")
    @classmethod
    def required_when_provided(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("필수 항목은 null일 수 없습니다.")
        return value


class AttachmentRead(Record):
    filename: str
    media_type: str
    size: int


class PostAttachmentRead(AttachmentRead):
    id: int


class PostSummary(Record):
    id: int
    author: Author
    title: str
    category: str
    audience: str
    scale: str
    region: str | None
    view_count: int
    created_at: datetime
    description: str = ""
    availability: str | None = None
    distance_km: int | None = None
    price: int | None = None
    instructor_kind: InstructorKind = "personal"
    instructor_organization: str | None = None
    comment_count: int = 0
    review_count: int = 0
    average_rating: float | None = None


class PostRead(PostSummary):
    body: str
    skills: str | None
    tech_stack: str | None
    availability: str | None
    duration_minutes: int | None
    additional_info: str | None
    updated_at: datetime
    attachments: list[PostAttachmentRead]


class CommentEdit(Input):
    body: CommentBody


class CommentInput(CommentEdit):
    parent_id: Identifier | None = None


class CommentRead(Record):
    id: int
    parent_id: int | None
    author: Author | None
    body: str | None
    deleted: bool
    created_at: datetime
    replies: list["CommentRead"] = []


class CommentList(Record):
    items: list[CommentRead]
    total: int


class ReactionInput(Input):
    value: Annotated[int, Field(strict=True, ge=-1, le=1)]

    @field_validator("value")
    @classmethod
    def nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("추천은 1, 비추천은 -1을 입력해주세요.")
        return value


class ReactionRead(Record):
    likes: int
    dislikes: int
    current: int | None


class ReviewInput(Input):
    rating: Rating
    body: LongNote


class ReviewPatch(Input):
    rating: Rating | None = None
    body: LongNote | None = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("별점 또는 내용을 입력해주세요.")
        return self


class ReviewRead(Record):
    id: int
    post_id: int
    author: Author
    rating: int
    body: str
    created_at: datetime
    updated_at: datetime
    post_title: str | None = None


class ReviewList(Page[ReviewRead]):
    average_rating: float | None


class InstructorSummary(Record):
    id: int
    name: str
    photo_url: str | None
    specialty: str | None
    experience: str | None
    bio: str | None
    organization: str | None
    kind: InstructorKind
    category: str | None
    skills: str | None
    audience: str | None
    distance_km: int | None


class InstructorRead(InstructorSummary):
    programs: Page[PostSummary]
    average_rating: float | None
    review_count: int


class ActivityRead(Record):
    id: int
    actor_id: int
    action: str
    resource: str
    resource_id: int
    created_at: datetime


class AccountCommentRead(Record):
    id: int
    post_id: int
    parent_id: int | None
    body: str
    created_at: datetime


class RoomCreate(Input):
    recipient_id: Identifier


class MessageFile(Input):
    filename: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    data_base64: Annotated[str, StringConstraints(min_length=4, max_length=6990508)]


class EnterRoom(Input):
    type: Literal["room.enter"]
    room_id: Identifier


class ExitRoom(Input):
    type: Literal["room.exit"]


class SendMessage(Input):
    type: Literal["message.send"]
    room_id: Identifier
    client_id: UUID
    body: CommentBody | None = None
    attachment: MessageFile | None = None

    @model_validator(mode="after")
    def require_content(self):
        if self.body is None and self.attachment is None:
            raise ValueError("내용이나 첨부파일을 입력해주세요.")
        return self


class MessageRead(Record):
    id: int
    room_id: int
    sender_id: int
    client_id: str
    body: str | None
    attachment: AttachmentRead | None
    created_at: datetime


class HistoryRead(Record):
    items: list[MessageRead]
    next_before_id: int | None


class RoomRead(Record):
    id: int
    counterpart: Author
    last_message: MessageRead | None
    unread_count: int
    created_at: datetime
