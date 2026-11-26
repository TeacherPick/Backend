import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote

from fastapi import Response, UploadFile

from app.core import AppError
from app.models import MessageAttachment, PostAttachment

MAX_FILE = 5 * 1024 * 1024
MAX_POST_FILES = 5
MAX_POST_JSON = 512 * 1024
MAX_UPLOAD_REQUEST = MAX_POST_FILES * MAX_FILE + MAX_POST_JSON + 64 * 1024

FILE_SIGNATURES = {
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".pdf": ("application/pdf", b"%PDF-"),
}


@dataclass(frozen=True)
class FileData:
    filename: str
    media_type: str
    size: int
    data: bytes


def validate_file(filename: str, data: bytes) -> FileData:
    if len(data) > MAX_FILE:
        raise AppError(413, "file_too_large", "첨부 가능한 용량을 초과했습니다.")
    filename = PurePosixPath(filename.replace("\\", "/")).name.strip()
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    info = FILE_SIGNATURES.get(PurePosixPath(filename).suffix.lower())
    if len(filename) > 255 or info is None or not data.startswith(info[1]):
        raise AppError(415, "invalid_file_type", "첨부할 수 없는 파일 형식입니다.")
    return FileData(filename, info[0], len(data), data)


async def read_post_files(files: list[UploadFile] | None) -> list[FileData]:
    files = files or []
    if len(files) > MAX_POST_FILES:
        raise AppError(422, "too_many_files", "게시물당 최대 5개까지 첨부할 수 있습니다.")
    return [validate_file(file.filename or "", await file.read(MAX_FILE + 1)) for file in files]


def download(file: PostAttachment | MessageAttachment) -> Response:
    return Response(
        file.data,
        media_type=file.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file.filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
        },
    )
