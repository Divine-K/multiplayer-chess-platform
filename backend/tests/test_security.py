from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_with_argon2_and_verifies() -> None:
    hashed = hash_password("a-strong-password")
    assert hashed != "a-strong-password"
    assert hashed.startswith("$argon2")
    assert verify_password("a-strong-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_same_password_produces_different_hashes() -> None:
    assert hash_password("repeat-me-please") != hash_password("repeat-me-please")


def test_access_token_round_trip() -> None:
    assert decode_access_token(create_access_token(42)) == 42


def test_expired_token_is_rejected() -> None:
    long_ago = datetime.now(UTC) - timedelta(days=2)
    with pytest.raises(InvalidTokenError):
        decode_access_token(create_access_token(1, now=long_ago))


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(1)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token[:-2] + ("AA" if not token.endswith("AA") else "BB"))


def test_token_signed_with_other_secret_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": "1", "type": "access", "iat": 1, "exp": 9_999_999_999},
        "some-other-secret-that-is-also-long-enough-1234",
        algorithm=get_settings().jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_token_of_wrong_type_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "1", "type": "refresh", "iat": 1, "exp": 9_999_999_999},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_unsigned_none_algorithm_token_is_rejected() -> None:
    token = jwt.encode({"sub": "1", "type": "access", "iat": 1, "exp": 9_999_999_999}, None, algorithm="none")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
