from collections import Counter
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Game, GameParticipant, GameStatus, MatchmakingEntry, PlayerColor
from app.services import game_service, matchmaking_service
from app.services.errors import AlreadyInGameError, AlreadyQueuedError, UnsupportedTimeControlError
from app.services.matchmaking_service import MatchmakingState
from tests.factories import at, make_user, run_concurrently

STALE = timedelta(seconds=15)


def join(session: Session, user_id: int, seconds: int = 300, now: datetime | None = None) -> MatchmakingState:
    return matchmaking_service.join_queue(
        session,
        user_id,
        time_control_seconds=seconds,
        increment_seconds=0,
        now=now or at(0),
        stale_after=STALE,
    )


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_two_players_are_paired_with_opposite_colors(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    assert join(db_session, a.id).status == "queued"
    matched = join(db_session, b.id)
    assert matched.status == "matched" and matched.game_id is not None

    for_a = matchmaking_service.poll_status(db_session, a.id, at(1))
    assert (for_a.status, for_a.game_id) == ("matched", matched.game_id)
    assert {for_a.color, matched.color} == {PlayerColor.WHITE, PlayerColor.BLACK}
    game = game_service.load_game(db_session, matched.game_id)
    assert game.status == GameStatus.WAITING and game.time_control_seconds == 300
    assert count(db_session, MatchmakingEntry) == 0


def test_colors_are_randomised(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    a_id, b_id = a.id, b.id
    seen: set[PlayerColor | None] = set()
    for _ in range(40):
        join(db_session, a_id)
        matched = join(db_session, b_id)
        seen.add(matched.color)
        assert matched.game_id is not None
        game_service.resign(db_session, matched.game_id, a_id, at(1))
        if len(seen) == 2:
            break
    assert seen == {PlayerColor.WHITE, PlayerColor.BLACK}


def test_longest_waiting_player_is_matched_first(db_session: Session) -> None:
    first, second, third = (make_user(db_session, n) for n in ("first", "second", "third"))
    join(db_session, first.id, now=at(0))
    # Seed a second waiter directly: joining normally would pair the two immediately.
    db_session.add(
        MatchmakingEntry(
            user_id=second.id, time_control_seconds=300, increment_seconds=0, joined_at=at(1), last_seen_at=at(1)
        )
    )
    db_session.commit()
    matched = join(db_session, third.id, now=at(2))
    assert matched.game_id is not None
    ids = {p.user_id for p in game_service.load_game(db_session, matched.game_id).participants}
    assert ids == {first.id, third.id}


def test_different_time_controls_are_not_paired(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    assert join(db_session, a.id, 180).status == "queued"
    assert join(db_session, b.id, 600).status == "queued"
    assert count(db_session, Game) == 0


def test_unsupported_time_control(db_session: Session) -> None:
    a = make_user(db_session, "a")
    with pytest.raises(UnsupportedTimeControlError):
        join(db_session, a.id, 7)


def test_duplicate_requests_are_rejected(db_session: Session) -> None:
    a = make_user(db_session, "a")
    a_id = a.id
    join(db_session, a_id)
    for seconds in (300, 180):
        with pytest.raises(AlreadyQueuedError):
            join(db_session, a_id, seconds)
    assert count(db_session, MatchmakingEntry) == 1


def test_cannot_queue_while_in_a_game(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    a_id = a.id
    join(db_session, a_id)
    join(db_session, b.id)
    with pytest.raises(AlreadyInGameError):
        join(db_session, a_id)


def test_cancel_removes_the_player(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    join(db_session, a.id)
    assert matchmaking_service.cancel(db_session, a.id).status == "idle"
    assert join(db_session, b.id).status == "queued"
    assert matchmaking_service.poll_status(db_session, a.id, at(1)).status == "idle"


def test_cancel_after_a_match_reports_the_game(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    join(db_session, a.id)
    matched = join(db_session, b.id)
    state = matchmaking_service.cancel(db_session, a.id)
    assert (state.status, state.game_id) == ("matched", matched.game_id)


def test_abandoned_entries_are_not_matched(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    join(db_session, a.id, now=at(0))
    assert join(db_session, b.id, now=at(16)).status == "queued"
    assert count(db_session, Game) == 0


def test_polling_keeps_a_queue_entry_alive(db_session: Session) -> None:
    a, b = make_user(db_session, "a"), make_user(db_session, "b")
    join(db_session, a.id, now=at(0))
    assert matchmaking_service.poll_status(db_session, a.id, at(10)).status == "queued"
    assert join(db_session, b.id, now=at(20)).status == "matched"


# ----- Concurrency ----------------------------------------------------------------------------


@pytest.mark.parametrize("attempt", range(3))
def test_simultaneous_joins_pair_everyone_exactly_once(db_session: Session, attempt: int) -> None:
    user_ids = [make_user(db_session, f"player{i}").id for i in range(20)]
    results = run_concurrently([lambda s, uid=uid: join(s, uid) for uid in user_ids])

    assert [r for r in results if isinstance(r, Exception)] == []
    assert Counter(r.status for r in results) == {"queued": 10, "matched": 10}
    assert count(db_session, Game) == 10
    assert count(db_session, MatchmakingEntry) == 0
    seats = db_session.scalars(select(GameParticipant.user_id)).all()
    assert sorted(seats) == sorted(user_ids)


def test_one_user_spamming_join_gets_a_single_entry(db_session: Session) -> None:
    uid = make_user(db_session, "spammer").id
    results = run_concurrently([lambda s: join(s, uid)] * 8)
    assert sum(isinstance(r, MatchmakingState) for r in results) == 1
    assert sum(isinstance(r, AlreadyQueuedError) for r in results) == 7
    assert count(db_session, MatchmakingEntry) == 1
