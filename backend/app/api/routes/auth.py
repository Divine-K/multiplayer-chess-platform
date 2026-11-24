from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services import user_service
from app.services.errors import DuplicateAccountError, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Username or email already registered"}},
    summary="Register a new player account",
)
def register(payload: RegisterRequest, session: DbSession) -> UserPublic:
    try:
        user = user_service.register_user(session, payload)
    except DuplicateAccountError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserPublic.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid email or password"}},
    summary="Exchange credentials for an access token",
)
def login(payload: LoginRequest, session: DbSession) -> TokenResponse:
    try:
        user = user_service.authenticate_user(
            session, str(payload.email), payload.password.get_secret_value()
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenResponse(access_token=create_access_token(user.id))
