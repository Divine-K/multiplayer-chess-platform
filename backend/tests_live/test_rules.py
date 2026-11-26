"""Chess rules, enforced by the server across two real connections."""

from collections.abc import Callable

import chess
import pytest

from tests_live import scripts_for_endings as endings
from tests_live.harness import Run, World


@pytest.mark.parametrize(
    ("moves", "result", "reason"),
    [
        (endings.FOOLS_MATE, "black_win", "checkmate"),
        (endings.SCHOLARS_MATE, "white_win", "checkmate"),
        (endings.STALEMATE, "draw", "stalemate"),
        (endings.THREEFOLD, "draw", "threefold_repetition"),
    ],
    ids=["checkmate_black_wins", "checkmate_white_wins", "stalemate", "threefold_repetition"],
)
def test_ending(run: Run, moves: str, result: str, reason: str) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all(moves)
        await match.finished(result, reason)
        await match.close()

    run(scenario)


@pytest.mark.parametrize(
    ("moves", "reason"),
    [
        (endings.insufficient_material_game, "insufficient_material"),
        (endings.fifty_move_game, "fifty_move_rule"),
    ],
    ids=["insufficient_material", "fifty_move_rule"],
)
def test_long_draw(run: Run, moves: Callable[[], tuple[str, ...]], reason: str) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all(" ".join(moves()))
        await match.finished("draw", reason)
        await match.close()

    run(scenario)


@pytest.mark.parametrize("seed", range(16))
def test_random_complete_game(run: Run, seed: int) -> None:
    moves, result, reason = endings.random_game(seed)

    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all(" ".join(moves))
        await match.finished(result, reason)
        await match.close()

    run(scenario)


@pytest.mark.parametrize(
    ("setup", "castle", "king", "rook"),
    [
        ("e2e4 e7e5 g1f3 b8c6 f1c4 f8c5", "e1g1", "g1", "f1"),
        ("e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3 f8c5 b1c3", "e8g8", "g8", "f8"),
        ("d2d4 d7d5 b1c3 b8c6 c1f4 c8f5 d1d2 d8d7", "e1c1", "c1", "d1"),
        ("d2d4 d7d5 b1c3 b8c6 c1f4 c8f5 d1d2 d8d7 a2a3", "e8c8", "c8", "d8"),
    ],
    ids=["white_kingside", "black_kingside", "white_queenside", "black_queenside"],
)
def test_castling(run: Run, setup: str, castle: str, king: str, rook: str) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all(setup)
        await match.play(castle)
        placed = {square: match.board.piece_at(chess.parse_square(square)) for square in (king, rook)}
        assert [str(placed[king]).lower(), str(placed[rook]).lower()] == ["k", "r"]
        await match.close()

    run(scenario)


def test_castling_through_check_is_rejected(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        # Black's bishop on a6 attacks f1, the square the white king would cross.
        await match.play_all("e2e4 b7b6 g1f3 c8a6 f1c4 e7e6 c4b3 d7d6")
        await match.reject(match.white, "e1g1", "illegal_move")
        await match.close()

    run(scenario)


def test_castling_after_the_king_moved_is_rejected(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 e1f1 a7a6 f1e1 a6a5")
        await match.reject(match.white, "e1g1", "illegal_move")
        await match.close()

    run(scenario)


@pytest.mark.parametrize(
    ("setup", "capture"),
    [("e2e4 a7a6 e4e5 d7d5", "e5d6"), ("a2a3 d7d5 h2h3 d5d4 e2e4", "d4e3")],
    ids=["by_white", "by_black"],
)
def test_en_passant(run: Run, setup: str, capture: str) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all(setup)
        state = await match.play(capture)
        capturer = "white" if capture == "e5d6" else "black"
        assert state["captured"][capturer] == ["p"]
        await match.close()

    run(scenario)


def test_en_passant_expires_after_one_move(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("e2e4 a7a6 e4e5 d7d5 h2h3 a6a5")
        await match.reject(match.white, "e5d6", "illegal_move")
        await match.close()

    run(scenario)


@pytest.mark.parametrize("piece", ["q", "r", "b", "n"])
def test_promotion(run: Run, piece: str) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("h2h4 g7g5 h4g5 g8f6 g5g6 f6e4 g6g7 e4f6")
        await match.reject(match.white, "g7h8", "promotion_required")
        state = await match.play(f"g7h8{piece}")
        assert state["moves"][-1]["san"].startswith(f"gxh8={piece.upper()}")
        await match.close()

    run(scenario)


def test_illegal_moves_are_rejected(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.reject(match.white, "e2e5", "illegal_move")  # pawn too far
        await match.reject(match.white, "d1d3", "illegal_move")  # through own pawn
        await match.reject(match.white, "z9e4", "invalid_move_format")
        await match.play_all("e2e4 e7e5 d2d4 f8b4")
        await match.reject(match.white, "a2a3", "illegal_move")  # ignores check
        await match.play("c2c3")
        await match.play("a7a6")
        await match.close()

    run(scenario)


def test_pinned_piece_cannot_move(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("d2d4 e7e6 b1c3 f8b4")
        await match.reject(match.white, "c3d5", "illegal_move")
        await match.close()

    run(scenario)


def test_turns_are_enforced(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.reject(match.black, "e7e5", "not_your_turn")
        await match.reject(match.white, "e7e5", "illegal_move")  # the opponent's piece
        await match.play("e2e4")
        await match.reject(match.white, "d2d4", "not_your_turn")
        await match.play("e7e5")
        await match.close()

    run(scenario)


def test_no_moves_after_the_game_ends(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all(endings.FOOLS_MATE)
        await match.finished("black_win", "checkmate")
        await match.reject(match.white, "a2a3", "game_not_active")
        await match.close()

    run(scenario)
