"""Shared fixtures. Tests run against a real PostgreSQL database, migrated with Alembic."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_test_environment() -> None:
    """Use CI-provided variables if present, otherwise fall back to backend/.env.test."""
    env_file = BACKEND_DIR / ".env.test"
    if "DATABASE_URL" in os.environ or not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_test_environment()
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-123456")

# Safety guard: never let the suite touch a non-test database.
_database_name = os.environ.get("DATABASE_URL", "").rsplit("/", 1)[-1]
if not _database_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests against database '{_database_name}'. "
        "Point DATABASE_URL at a database whose name ends in '_test'."
    )

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_engine, get_session_factory
from app.main import create_app

TABLES = "player_statistics, moves, game_participants, games, users"


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    """Build the schema from scratch via migrations, exercising upgrade and downgrade."""
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


VALID_USER = {"username": "magnus_c", "email": "magnus@example.com", "password": "correct-horse-battery"}


@pytest.fixture
def registered_user(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json=VALID_USER)
    assert response.status_code == 201
    return VALID_USER


@pytest.fixture
def auth_headers(client: TestClient, registered_user: dict[str, str]) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
