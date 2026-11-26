from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import Settings
from app.core.time import utc_now
from app.schemas.matchmaking import MatchmakingRequest, MatchmakingResponse, TimeControlInfo
from app.services import matchmaking_service
from app.services.errors import AlreadyInGameError, AlreadyQueuedError, UnsupportedTimeControlError
from app.services.time_controls import TIME_CONTROLS

router = APIRouter(prefix="/matchmaking", tags=["matchmaking"])


@router.get("/time-controls", response_model=list[TimeControlInfo], summary="List offered time controls")
def list_time_controls() -> list[TimeControlInfo]:
    return [TimeControlInfo.model_validate(option, from_attributes=True) for option in TIME_CONTROLS]


@router.post(
    "",
    response_model=MatchmakingResponse,
    responses={409: {"description": "Already searching, or already in a game"}},
    summary="Search for a game (creates the game when an opponent is waiting)",
)
def join(
    payload: MatchmakingRequest, user: CurrentUser, session: DbSession, request: Request
) -> MatchmakingResponse:
    settings: Settings = request.app.state.settings
    user_id = user.id
    try:
        state = matchmaking_service.join_queue(
            session,
            user_id,
            time_control_seconds=payload.time_control_seconds,
            increment_seconds=payload.increment_seconds,
            now=utc_now(),
            stale_after=timedelta(seconds=settings.matchmaking_stale_seconds),
        )
    except UnsupportedTimeControlError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except (AlreadyQueuedError, AlreadyInGameError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if state.status == "matched":
        request.app.state.commands.games_pending.set()
    return MatchmakingResponse.model_validate(state, from_attributes=True)


@router.get(
    "/status",
    response_model=MatchmakingResponse,
    summary="Check search progress. Poll while searching: it keeps your queue entry alive.",
)
def read_status(user: CurrentUser, session: DbSession) -> MatchmakingResponse:
    state = matchmaking_service.poll_status(session, user.id, utc_now())
    return MatchmakingResponse.model_validate(state, from_attributes=True)


@router.delete(
    "",
    response_model=MatchmakingResponse,
    summary="Stop searching. Returns 'matched' if a game was created first.",
)
def cancel(user: CurrentUser, session: DbSession) -> MatchmakingResponse:
    state = matchmaking_service.cancel(session, user.id)
    return MatchmakingResponse.model_validate(state, from_attributes=True)
