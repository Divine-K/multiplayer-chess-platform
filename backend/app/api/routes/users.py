from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import UserPublic
from app.schemas.game import PublicProfile, Statistics
from app.services import game_queries
from app.services.errors import UserNotFoundError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic, summary="Return the authenticated user's profile")
def read_current_user(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.get("/me/statistics", response_model=Statistics, summary="Your win/loss/draw record")
def read_own_statistics(current_user: CurrentUser, session: DbSession) -> Statistics:
    return game_queries.statistics_for(session, current_user.id)


@router.get(
    "/{username}",
    response_model=PublicProfile,
    responses={404: {"description": "Player not found"}},
    summary="A player's public profile and record",
)
def read_profile(username: str, current_user: CurrentUser, session: DbSession) -> PublicProfile:
    try:
        return game_queries.public_profile(session, username)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
