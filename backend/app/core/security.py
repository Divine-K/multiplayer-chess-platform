"""Password hashing and JWT access-token helpers. Pure functions, no database access."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hasher = PasswordHash.recommended()  # Argon2id with library-maintained parameters

TOKEN_TYPE_ACCESS = "access"


class InvalidTokenError(Exception):
    """Raised when a token is malformed, tampered with, expired or of the wrong type."""


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _password_hasher.verify(plain_password, password_hash)


def create_access_token(subject_user_id: int, *, now: datetime | None = None) -> str:
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    claims: dict[str, Any] = {
        "sub": str(subject_user_id),
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """Return the user id encoded in a valid access token, or raise InvalidTokenError."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid or expired token.") from exc

    if claims.get("type") != TOKEN_TYPE_ACCESS:
        raise InvalidTokenError("Unexpected token type.")
    try:
        return int(claims["sub"])
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("Malformed subject claim.") from exc
