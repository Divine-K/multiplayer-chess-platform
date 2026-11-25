"""Game endpoints. Games are created by matchmaking; moves are played over the WebSocket."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.time import utc_now
from app.models import Game
from app.realtime.commands import GameCommands
from app.schemas.game import GameHistoryPage, GameResultInfo, GameState
from app.services import game_queries, game_service
from app.services.errors import GameNotActiveError, GameNotFoundError, NotAParticipantError

router = APIRouter(prefix="/games", tags=["games"])

GAME_ERRORS: dict[int | str, dict[str, str]] = {
    403: {"description": "You are not a player in this game"},
    404: {"description": "Game not found"},
}


def _load_own_game(session: DbSession, game_id: uuid.UUID, user_id: int) -> Game:
    try:
        game = game_service.load_game(session, game_id)
        game_service.participant_for(game, user_id)
    except GameNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except NotAParticipantError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return game


@router.get("/active", response_model=GameState | None, summary="Your unfinished game, or null")
def read_active_game(user: CurrentUser, session: DbSession) -> GameState | None:
    active = game_queries.find_active_game(session, user.id)
    if active is None:
        return None
    return game_queries.build_state(game_service.load_game(session, active[0]), utc_now())


@router.get("/history", response_model=GameHistoryPage, summary="Your finished games, newest first")
def read_history(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> GameHistoryPage:
    return game_queries.match_history(session, user.id, limit=limit, offset=offset)


@router.get("/{game_id}", response_model=GameState, responses=GAME_ERRORS, summary="Full game state")
def read_game(game_id: uuid.UUID, user: CurrentUser, session: DbSession) -> GameState:
    return game_queries.build_state(_load_own_game(session, game_id, user.id), utc_now())


@router.get(
    "/{game_id}/result", response_model=GameResultInfo, responses=GAME_ERRORS, summary="A game's result"
)
def read_result(game_id: uuid.UUID, user: CurrentUser, session: DbSession) -> GameResultInfo:
    game = _load_own_game(session, game_id, user.id)
    return GameResultInfo(
        game_id=game.id,
        status=game.status,
        result=game.result,
        result_reason=game.result_reason,
        finished_at=game.finished_at,
    )


@router.post(
    "/{game_id}/resign",
    response_model=GameState,
    responses=GAME_ERRORS | {409: {"description": "The game is already over"}},
    summary="Resign (or leave a game that has not started)",
)
async def resign_game(game_id: uuid.UUID, user: CurrentUser, request: Request) -> GameState:
    commands: GameCommands = request.app.state.commands
    try:
        return await commands.resign(game_id, user.id)
    except GameNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except NotAParticipantError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except GameNotActiveError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
