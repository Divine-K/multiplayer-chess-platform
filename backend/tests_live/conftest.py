"""Match tests against a real API process. Run with: pytest tests_live

Uses the `_test` database from the environment or backend/.env.test. A summary of the games that
were really played is written to the path in MATCH_REPORT (default: tests_live/match-report.json).
"""

import asyncio
import json
import os
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from tests_live.harness import BACKEND_DIR, ORIGIN, ApiServer, Run, Scenario, SessionLog, world_for


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    env_file = BACKEND_DIR / ".env.test"
    if not url and env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, value = line.strip().partition("=")
            if key == "DATABASE_URL":
                url = value
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        raise RuntimeError("Match tests need a DATABASE_URL whose database name ends in '_test'.")
    return url


SESSIONS = SessionLog()
OUTCOMES: Counter[str] = Counter()


@pytest.fixture(scope="session")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ApiServer]:
    env = {
        "DATABASE_URL": _database_url(),
        "ENVIRONMENT": "test",
        "JWT_SECRET_KEY": "live-test-only-secret-key-long-enough-1234567",
        "CORS_ORIGINS": json.dumps([ORIGIN]),
        # Short enough to observe an abandoned game without waiting a minute.
        "GAME_START_TIMEOUT_SECONDS": "8",
        # Every test user signs up from the same address; the limiter has its own unit tests.
        "AUTH_RATE_LIMIT_PER_MINUTE": "100000",
    }
    os.environ.update(env)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    api = ApiServer(env, tmp_path_factory.mktemp("api") / "api.log")
    api.start()
    try:
        yield api
    finally:
        api.stop()
        errors = [
            line for line in api.log_path.read_text().splitlines() if "Traceback" in line or "ERROR" in line
        ]
        assert not errors, f"The API logged errors; see {api.log_path}: {errors[:5]}"


@pytest.fixture
def run(server: ApiServer, request: pytest.FixtureRequest) -> Run:
    SESSIONS.scenario = request.node.name

    def _run(scenario: Scenario) -> None:
        async def main() -> None:
            async with world_for(server, SESSIONS) as world:
                await scenario(world)

        asyncio.run(main())

    return _run


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when == "call":
        OUTCOMES[report.outcome] += 1


def pytest_sessionfinish() -> None:
    if not SESSIONS.entries:
        return
    entries = SESSIONS.entries.values()
    summary = {
        "tests": dict(OUTCOMES),
        "match_sessions": len(entries),
        "scenarios_with_a_match": len({e["scenario"] for e in entries}),
        "moves_accepted": sum(e["plies"] for e in entries),
        "endings": dict(Counter(f"{e['status']}:{e.get('reason')}" for e in entries)),
        "sessions_per_scenario": dict(Counter(e["scenario"] for e in entries)),
    }
    path = Path(os.environ.get("MATCH_REPORT", BACKEND_DIR / "tests_live" / "match-report.json"))
    path.write_text(json.dumps(summary, indent=2) + "\n")
