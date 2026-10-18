"""Alembic environment: migrations always run on DATABASE_URL_BI, and the product's tables live
in the standard schema `public` (tests redirect everything to a temporary app_test_* schema).

Autogenerate only ever considers the tables defined in app.models, so any other table that may
exist in the database is never altered or dropped.
"""
from logging.config import fileConfig

from sqlalchemy import text

from alembic import context
from app.config import get_settings
from app.db import get_engine
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

TARGET_SCHEMA = get_settings().db_schema  # validated: "public" or "app_test_*"
IS_TEST = TARGET_SCHEMA != "public"


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in Base.metadata.tables or name == "alembic_version"
    return True


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection") or get_engine()
    with connectable.connect() as connection:
        if IS_TEST:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TARGET_SCHEMA}"'))
            connection.commit()
            # Fail closed: unqualified DDL must never reach the real public schema.
            current = connection.execute(text("SELECT current_schema()")).scalar()
            if current != TARGET_SCHEMA:
                raise SystemExit(f"refusing to migrate: current schema is {current!r}, "
                                 f"expected {TARGET_SCHEMA!r}")
            connection.commit()  # end the check's transaction so Alembic owns the next one
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            version_table_schema=TARGET_SCHEMA if IS_TEST else None,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode is not supported; run against a database.")
run_migrations_online()
