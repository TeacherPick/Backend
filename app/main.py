import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.router import router
from app.core import AppError, Settings, get_settings
from app.db import make_engine
from app.services.files import MAX_POST_JSON, MAX_UPLOAD_REQUEST

logger = logging.getLogger(__name__)
TOO_LARGE = "request_body_limit_exceeded"


class ErrorDetail(BaseModel):
    code: str
    message: str
    issues: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(
    status: int, code: str, message: str, *, issues: list[dict] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    content = {"code": code, "message": message}
    if issues is not None:
        content["issues"] = issues
    return JSONResponse({"error": content}, status_code=status, headers=headers)


class RequestBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        multipart = headers.get(b"content-type", b"").lower().startswith(b"multipart/form-data")
        limit = 256 * 1024
        if scope["path"].startswith("/api/v1/posts"):
            limit = MAX_UPLOAD_REQUEST if multipart else MAX_POST_JSON
        length = headers.get(b"content-length", b"")
        if length.isdigit() and int(length) > limit:
            await error_response(413, "request_too_large", "요청 용량을 초과했습니다.")(scope, receive, send)
            return

        received = 0
        exceeded = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            frame = await receive()
            received += len(frame.get("body", b""))
            if received > limit:
                exceeded = True
                raise MultiPartException(TOO_LARGE)
            return frame

        async def limited_send(frame: Message) -> None:
            if frame["type"] == "http.response.start":
                if exceeded:
                    await error_response(413, "request_too_large", "요청 용량을 초과했습니다.")(scope, receive, send)
                    return
                frame["headers"] = [*frame["headers"], (b"cache-control", b"no-store")]
            if not exceeded:
                await send(frame)

        await self.app(scope, limited_receive, limited_send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings)
        app.state.sessions = sessionmaker(engine, expire_on_commit=False)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="강사 프로그램 플랫폼",
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=[{
            "name": "DM",
            "description": "실시간 대화는 WebSocket /api/v1/dm/ws를 사용합니다. 메시지 계약은 README의 DM 문서를 참고하세요.",
        }],
    )
    app.state.settings = settings
    app.add_middleware(RequestBodyLimit)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"],
            expose_headers=["Content-Disposition", "Retry-After"],
        )

    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [{"location": issue["loc"], "type": issue["type"]} for issue in exc.errors()]
        return error_response(422, "validation_error", "입력값을 확인해주세요.", issues=issues)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "요청을 처리할 수 없습니다."
        return error_response(exc.status_code, "http_error", detail, headers=exc.headers)

    @app.exception_handler(MultiPartException)
    async def multipart_error(_request: Request, exc: MultiPartException) -> JSONResponse:
        return error_response(400, "invalid_multipart", exc.message)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("Database operation failed (%s)", type(exc).__name__)
        if isinstance(exc, OperationalError):
            errno = exc.orig.args[0] if exc.orig.args else None
            if errno in (1205, 1213):
                return error_response(409, "retry_transaction", "요청이 충돌했습니다. 다시 시도해주세요.")
            if exc.connection_invalidated or errno in (1040, 1045, 1049, 2002, 2003, 2006, 2013):
                return error_response(503, "database_unavailable", "현재 데이터를 처리할 수 없습니다.")
        return error_response(500, "database_error", "데이터 처리 중 오류가 발생했습니다.")

    app.include_router(router, responses={
        401: {"model": ErrorResponse, "description": "로그인 필요 또는 자격 증명 오류"},
        403: {"model": ErrorResponse, "description": "권한 없음"},
        422: {"model": ErrorResponse, "description": "입력값 오류"},
    })
    return app


app = create_app()
