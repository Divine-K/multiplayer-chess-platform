"""Abuse limits, production settings and response headers."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings, get_settings
from app.core.rate_limit import SlidingWindowLimiter
from app.main import create_app

SECRET = "a-perfectly-good-secret-value-0123456789"


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": get_settings().database_url,
        "jwt_secret_key": SECRET,
    } | overrides
    return Settings(_env_file=None, **values)


def test_limiter_blocks_then_recovers() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(2, 60, clock=lambda: now[0])
    assert limiter.retry_after("a") == 0
    now[0] = 10
    assert limiter.retry_after("a") == 0
    assert limiter.retry_after("a") == 50
    assert limiter.retry_after("b") == 0  # other clients are unaffected
    now[0] = 60
    assert limiter.retry_after("a") == 0


def test_repeated_sign_in_attempts_are_refused() -> None:
    body = {"email": "nobody@example.com", "password": "wrong-password"}
    with TestClient(create_app(settings(auth_rate_limit_per_minute=3))) as client:
        codes = [client.post("/api/v1/auth/login", json=body).status_code for _ in range(4)]
        blocked = client.post("/api/v1/auth/login", json=body)
        other_endpoint = client.post("/api/v1/auth/register", json={})

    assert codes == [401, 401, 401, 429]
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert other_endpoint.status_code == 422


@pytest.mark.parametrize(("hops", "last_status"), [(0, 429), (1, 429)])
def test_invented_forwarded_addresses_do_not_evade_the_limit(hops: int, last_status: int) -> None:
    body = {"email": "nobody@example.com", "password": "wrong-password"}
    app = create_app(settings(auth_rate_limit_per_minute=2, trusted_proxy_hops=hops))
    with TestClient(app) as client:
        codes = [
            client.post(
                "/api/v1/auth/login",
                json=body,
                # The caller invents the left part; a trusted proxy appends the real address.
                headers={"X-Forwarded-For": f"10.0.0.{n}, 203.0.113.9"},
            ).status_code
            for n in range(3)
        ]
    assert codes[-1] == last_status


def test_behind_a_proxy_each_real_client_has_its_own_limit() -> None:
    body = {"email": "nobody@example.com", "password": "wrong-password"}
    app = create_app(settings(auth_rate_limit_per_minute=1, trusted_proxy_hops=1))
    with TestClient(app) as client:
        codes = [
            client.post(
                "/api/v1/auth/login", json=body, headers={"X-Forwarded-For": f"203.0.113.{n}"}
            ).status_code
            for n in (1, 2, 1)
        ]
    assert codes == [401, 401, 429]


def test_waiting_unauthenticated_sockets_are_capped() -> None:
    path = "/ws/games/00000000-0000-0000-0000-000000000000"
    with TestClient(create_app(settings(ws_max_unauthenticated=1))) as client:
        with (
            client.websocket_connect(path),
            client.websocket_connect(path) as second,
            pytest.raises(WebSocketDisconnect) as closed,
        ):
            second.receive_json()
        assert closed.value.code == 4429


def test_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/matchmaking/time-controls")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://", "postgresql+psycopg://"])
def test_hosted_database_urls_select_the_installed_driver(prefix: str) -> None:
    assert settings(database_url=f"{prefix}u:p@host/db").database_url == "postgresql+psycopg://u:p@host/db"


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret_key": "change-me-change-me-change-me-change-me"},
        {"jwt_secret_key": "replace-with-at-least-32-random-characters-xxxx"},
        {"jwt_secret_key": "generate-with-python-secrets-token_urlsafe-48"},
        {"cors_origins": ["*"]},
    ],
)
def test_production_refuses_unsafe_settings(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        settings(environment="production", **overrides)
