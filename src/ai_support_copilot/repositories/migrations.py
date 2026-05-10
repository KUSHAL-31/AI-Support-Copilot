from pathlib import Path

from alembic import command
from alembic.config import Config

from ai_support_copilot.core.config import get_settings


def alembic_config(database_url: str | None = None) -> Config:
    project_root = Path.cwd()
    if not (project_root / "alembic.ini").exists():
        project_root = Path(__file__).resolve().parents[3]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        database_url or get_settings().postgres_dsn,
    )
    return config


def run_migrations(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")


if __name__ == "__main__":
    run_migrations()
