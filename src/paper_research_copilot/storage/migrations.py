"""Programmatic Alembic entry point for the application-owned SQLite schema."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL

MIGRATIONS_DIR = Path(__file__).resolve().parent / "alembic"


def upgrade_database(path: Path) -> None:
    database_path = path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option(
        "sqlalchemy.url",
        URL.create("sqlite+pysqlite", database=str(database_path)).render_as_string(
            hide_password=False
        ),
    )
    command.upgrade(config, "head")
