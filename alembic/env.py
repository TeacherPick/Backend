from alembic import context

from app import models
from app.core import get_settings
from app.db import make_engine

target_metadata = models.Base.metadata


def run_offline() -> None:
    context.configure(
        url=get_settings().database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = make_engine(get_settings())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_server_default=True,
                autogenerate_plugins=[
                    "alembic.autogenerate.*",
                    "alembic.ext.checkconstraint_byname",
                ],
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
