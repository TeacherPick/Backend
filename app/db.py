from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.core import Settings


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


def make_engine(settings: Settings) -> Engine:
    connect_args = {"connect_timeout": 5, "read_timeout": 15, "write_timeout": 15}
    if settings.db_ssl_ca:
        connect_args["ssl"] = {"ca": settings.db_ssl_ca, "check_hostname": True}
    engine = create_engine(
        settings.database_url(),
        connect_args=connect_args,
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,
    )

    @event.listens_for(engine, "connect")
    def set_time_zone(connection, _record) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")

    return engine


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session
