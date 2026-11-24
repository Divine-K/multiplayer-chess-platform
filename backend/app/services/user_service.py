"""User account use cases: registration and credential authentication."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import PlayerStatistics, User
from app.schemas.auth import RegisterRequest
from app.services.errors import DuplicateAccountError, InvalidCredentialsError

# Used to keep login timing roughly constant when the email is unknown, so response
# time does not reveal which email addresses are registered.
_TIMING_PADDING_HASH = hash_password("timing-padding-password-never-used")


def register_user(session: Session, data: RegisterRequest) -> User:
    """Create a user and an empty statistics row in one transaction."""
    user = User(
        username=data.username,
        email=str(data.email).lower(),
        password_hash=hash_password(data.password.get_secret_value()),
    )
    user.statistics = PlayerStatistics()
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateAccountError("Username or email is already registered.") from exc
    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> User:
    """Return the active user matching the credentials, or raise InvalidCredentialsError."""
    user = session.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        verify_password(password, _TIMING_PADDING_HASH)
        raise InvalidCredentialsError("Invalid email or password.")

    if not verify_password(password, user.password_hash) or not user.is_active:
        raise InvalidCredentialsError("Invalid email or password.")
    return user


def get_active_user_by_id(session: Session, user_id: int) -> User | None:
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user
