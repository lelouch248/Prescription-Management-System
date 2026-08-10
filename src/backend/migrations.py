from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection

from .models import Base


def migration_1(connection: Connection) -> None:
    """Initial canonical schema and replaceable full-text search index."""
    Base.metadata.create_all(connection)
    connection.exec_driver_sql(
        "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(entity_type UNINDEXED, entity_id UNINDEXED, profile_id UNINDEXED, title, content, event_date UNINDEXED, tokenize='unicode61 remove_diacritics 2')"
    )


MIGRATIONS: dict[int, Callable[[Connection], None]] = {1: migration_1}


def apply_migrations(connection: Connection, current: int, target: int) -> None:
    for version in range(current + 1, target + 1):
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise RuntimeError(f"Missing database migration {version}")
        with connection.begin_nested():
            migration(connection)
            connection.exec_driver_sql(
                "INSERT INTO schema_meta(key,value) VALUES('database_schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(version),),
            )
