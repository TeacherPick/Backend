import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "instructor_platform"
    db_user: str = "instructor_api"
    db_password: SecretStr = SecretStr("")
    db_ssl_ca: str | None = None
    session_minutes: int = Field(default=480, ge=1, le=1440)
    reset_code_pepper: SecretStr = SecretStr("")
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_security: Literal["starttls", "implicit"] = "starttls"
    smtp_username: str | None = None
    smtp_password: SecretStr = SecretStr("")
    smtp_sender: str | None = None
    cors_origins: list[str] = []

    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def code_digest(pepper: str, context: bytes, code: str) -> bytes:
    return hmac.digest(pepper.encode(), context + code.encode(), "sha256")


password_hasher = PasswordHasher()
dummy_password_hash = password_hasher.hash(secrets.token_urlsafe())


def password_matches(stored: str | None, supplied: str) -> bool:
    try:
        verified = password_hasher.verify(stored or dummy_password_hash, supplied)
    except VerificationError:
        return False
    return stored is not None and verified
