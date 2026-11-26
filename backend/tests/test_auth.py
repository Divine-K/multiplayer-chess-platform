import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PlayerStatistics, User
from tests.conftest import VALID_USER

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/users/me"


def test_register_creates_user_without_exposing_password(client: TestClient) -> None:
    response = client.post(REGISTER, json=VALID_USER)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == VALID_USER["username"]
    assert body["email"] == VALID_USER["email"]
    assert "password" not in body and "password_hash" not in body


def test_register_stores_only_a_hash_and_creates_statistics(client: TestClient, db_session: Session) -> None:
    client.post(REGISTER, json=VALID_USER)
    user = db_session.scalar(select(User).where(User.email == VALID_USER["email"]))
    assert user is not None
    assert user.password_hash != VALID_USER["password"]
    assert user.password_hash.startswith("$argon2")
    stats = db_session.get(PlayerStatistics, user.id)
    assert stats is not None and stats.games_played == 0


def test_register_normalises_email_case(client: TestClient) -> None:
    client.post(REGISTER, json={**VALID_USER, "email": "Magnus@Example.COM"})
    response = client.post(LOGIN, json={"email": "magnus@example.com", "password": VALID_USER["password"]})
    assert response.status_code == 200


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    client.post(REGISTER, json=VALID_USER)
    response = client.post(REGISTER, json={**VALID_USER, "username": "someone_else"})
    assert response.status_code == 409


def test_duplicate_username_is_rejected(client: TestClient) -> None:
    client.post(REGISTER, json=VALID_USER)
    response = client.post(REGISTER, json={**VALID_USER, "email": "other@example.com"})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "override",
    [
        {"password": "short"},
        {"email": "not-an-email"},
        {"username": "ab"},
        {"username": "has spaces"},
        {"username": "x" * 33},
    ],
)
def test_register_validates_input(client: TestClient, override: dict[str, str]) -> None:
    response = client.post(REGISTER, json={**VALID_USER, **override})
    assert response.status_code == 422


def test_register_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post(REGISTER, json={**VALID_USER, "is_active": False})
    assert response.status_code == 422


def test_login_returns_bearer_token(client: TestClient, registered_user: dict[str, str]) -> None:
    response = client.post(
        LOGIN, json={"email": registered_user["email"], "password": registered_user["password"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_with_wrong_password_fails(client: TestClient, registered_user: dict[str, str]) -> None:
    response = client.post(LOGIN, json={"email": registered_user["email"], "password": "wrong-password"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_error_does_not_reveal_whether_email_exists(
    client: TestClient, registered_user: dict[str, str]
) -> None:
    wrong_password = client.post(
        LOGIN, json={"email": registered_user["email"], "password": "nope-nope-nope"}
    )
    unknown_email = client.post(LOGIN, json={"email": "ghost@example.com", "password": "nope-nope-nope"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_current_user_requires_authentication(client: TestClient) -> None:
    response = client.get(ME)
    assert response.status_code == 401


def test_current_user_returns_profile(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(ME, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == VALID_USER["username"]


def test_current_user_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(ME, headers={"Authorization": "Bearer not.a.real-token"})
    assert response.status_code == 401


def test_deactivated_user_token_is_rejected(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    user = db_session.scalar(select(User))
    assert user is not None
    user.is_active = False
    db_session.commit()
    assert client.get(ME, headers=auth_headers).status_code == 401


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("register", {"username": "someone", "email": "a@example.com", "password": "s3cr3t!"}),
        ("register", {"username": "someone", "password": "a-long-secret-value"}),
        ("register", {"username": "someone", "email": "a@example.com", "password": "a-secret", "x": 1}),
        ("login", {"email": "not-an-email", "password": "a-long-secret-value"}),
    ],
    ids=["short_password", "missing_field", "extra_field", "bad_email"],
)
def test_validation_errors_never_repeat_the_password(
    client: TestClient, path: str, body: dict[str, object]
) -> None:
    response = client.post(f"/api/v1/auth/{path}", json=body)

    assert response.status_code == 422
    assert str(body["password"]) not in response.text
    assert all(set(problem) == {"type", "loc", "msg"} for problem in response.json()["detail"])
