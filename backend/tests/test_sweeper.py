import asyncio
import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import GameStatus
from app.realtime.commands import GameCommands
from app.realtime.connections import ConnectionManager
from app.realtime.sweeper import Sweeper
from app.services import game_service
from tests.factories import make_game, make_user


def test_one_failing_game_does_not_block_the_others(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Games started at T0, far in the past, so both clocks have long expired.
    games = [
        make_game(db_session, make_user(db_session, f"w{i}"), make_user(db_session, f"b{i}"))
        for i in range(2)
    ]
    commands = GameCommands(ConnectionManager())
    real_expire = commands.expire
    attempted: list[uuid.UUID] = []

    async def fail_on_first(game_id: uuid.UUID) -> None:
        attempted.append(game_id)
        if len(attempted) == 1:
            raise RuntimeError("simulated failure")
        await real_expire(game_id)

    monkeypatch.setattr(commands, "expire", fail_on_first)
    asyncio.run(Sweeper(commands, get_settings()).sweep())

    assert sorted(attempted) == sorted(games)
    db_session.expire_all()
    statuses = {game_id: game_service.load_game(db_session, game_id).status for game_id in games}
    assert statuses[attempted[0]] == GameStatus.ACTIVE
    assert statuses[attempted[1]] == GameStatus.FINISHED
