from typing import Annotated, Literal, TypeVar

from fastapi import Path, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.core import AppError
from app.schemas import PostInput, PostPatch
from app.services.files import FileData, MAX_POST_FILES, MAX_POST_JSON, read_post_files

Id = Annotated[int, Path(gt=0, le=9223372036854775807)]
PageNumber = Annotated[int, Query(ge=1, le=100000)]
PageSize = Annotated[int, Query(ge=1, le=100)]
SearchText = Annotated[str | None, Query(min_length=1, max_length=200)]
FilterText = Annotated[str | None, Query(min_length=1, max_length=100)]
ReviewSort = Literal["latest", "rating"]
Payload = TypeVar("Payload", PostInput, PostPatch)


def _validate_json(schema: type[Payload], raw: str | bytes) -> Payload:
    try:
        return schema.model_validate_json(raw)
    except ValidationError as exc:
        errors = [{**item, "loc": ("body", *item["loc"])} for item in exc.errors(include_input=False)]
        raise RequestValidationError(errors) from exc


async def parse_post(request: Request, schema: type[Payload]) -> tuple[Payload, list[FileData]]:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type == "application/json":
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_POST_JSON:
                raise AppError(413, "request_too_large", "요청 용량을 초과했습니다.")
        return _validate_json(schema, bytes(raw)), []
    if media_type != "multipart/form-data":
        raise AppError(415, "unsupported_request_type", "JSON 또는 multipart/form-data를 사용해주세요.")
    async with request.form(max_files=MAX_POST_FILES, max_fields=1, max_part_size=MAX_POST_JSON) as form:
        raw = form.get("data")
        files = form.getlist("files")
        if not isinstance(raw, str) or any(not isinstance(file, UploadFile) for file in files):
            raise AppError(422, "invalid_multipart", "data에 JSON을 입력하고 files에 파일을 첨부해주세요.")
        if set(form) - {"data", "files"}:
            raise AppError(422, "unknown_multipart_field", "허용되지 않은 입력 항목입니다.")
        return _validate_json(schema, raw), await read_post_files(files)


def post_request_schema(schema: type[PostInput] | type[PostPatch]) -> dict:
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": schema.model_json_schema()},
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["data"],
                        "properties": {
                            "data": {
                                "type": "string",
                                "description": "application/json의 스키마를 따르는 JSON 문자열",
                            },
                            "files": {
                                "type": "array",
                                "maxItems": MAX_POST_FILES,
                                "items": {"type": "string", "format": "binary"},
                            },
                        },
                    },
                },
            },
        },
    }


FILE_RESPONSES = {
    200: {
        "description": "첨부파일 다운로드",
        "content": {
            media_type: {"schema": {"type": "string", "format": "binary"}}
            for media_type in ("image/png", "image/jpeg", "application/pdf")
        },
    }
}
