import chess
import pytest

from app.chess_core.engine import (
    ChessEngine,
    IllegalMoveError,
    InvalidMoveFormatError,
    PromotionRequiredError,
)
from app.models import GameResult, PlayerColor, ResultReason


def play(engine: ChessEngine, *moves: str) -> ChessEngine:
    for uci in moves:
        engine.apply_move(uci[:2], uci[2:4], uci[4:] or None)
    return engine


def test_initial_position() -> None:
    engine = ChessEngine()
    assert engine.fen == chess.STARTING_FEN
    assert engine.turn == PlayerColor.WHITE
    assert len(engine.legal_moves()) == 20
    assert engine.last_move_uci is None
    assert engine.detect_end() is None


def test_legal_move_updates_board_and_turn() -> None:
    engine = ChessEngine()
    applied = engine.apply_move("e2", "e4")
    assert applied.uci == "e2e4"
    assert applied.san == "e4"
    assert not applied.is_capture
    assert engine.turn == PlayerColor.BLACK
    assert engine.last_move_uci == "e2e4"


@pytest.mark.parametrize("move", ["e2e5", "e1e2", "b1d2", "a1a3"])
def test_illegal_moves_are_rejected_and_leave_board_unchanged(move: str) -> None:
    engine = ChessEngine()
    with pytest.raises(IllegalMoveError):
        play(engine, move)
    assert engine.fen == chess.STARTING_FEN


def test_cannot_move_out_of_turn() -> None:
    with pytest.raises(IllegalMoveError):
        play(ChessEngine(), "e7e5")


@pytest.mark.parametrize(("source", "target"), [("z9", "e4"), ("e2", "e44"), ("", "e4")])
def test_malformed_squares_are_rejected(source: str, target: str) -> None:
    with pytest.raises(InvalidMoveFormatError):
        ChessEngine().apply_move(source, target)


def test_captures_are_recorded_per_side() -> None:
    engine = play(ChessEngine(), "e2e4", "d7d5")
    applied = engine.apply_move("e4", "d5")
    assert applied.is_capture
    engine.apply_move("d8", "d5")
    assert engine.captured_by(PlayerColor.WHITE) == ["p"]
    assert engine.captured_by(PlayerColor.BLACK) == ["p"]


@pytest.mark.parametrize(
    ("king_to", "san", "rook_square"), [("g1", "O-O", chess.F1), ("c1", "O-O-O", chess.D1)]
)
def test_castling_moves_king_and_rook(king_to: str, san: str, rook_square: chess.Square) -> None:
    engine = ChessEngine(starting_fen="r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    applied = engine.apply_move("e1", king_to)
    assert applied.san.rstrip("+") == san
    assert chess.Board(engine.fen).piece_at(rook_square) == chess.Piece(chess.ROOK, chess.WHITE)


def test_cannot_castle_through_check() -> None:
    # A black rook on f8 attacks f1, which the white king would have to cross.
    engine = ChessEngine(starting_fen="4kr2/8/8/8/8/8/8/4K2R w K - 0 1")
    with pytest.raises(IllegalMoveError):
        engine.apply_move("e1", "g1")


def test_en_passant_capture() -> None:
    engine = play(ChessEngine(), "e2e4", "a7a6", "e4e5", "d7d5")
    applied = engine.apply_move("e5", "d6")
    assert applied.is_capture
    assert engine.captured_by(PlayerColor.WHITE) == ["p"]
    assert chess.Board(engine.fen).piece_at(chess.D5) is None


def test_en_passant_expires_after_one_move() -> None:
    engine = play(ChessEngine(), "e2e4", "a7a6", "e4e5", "d7d5", "h2h3", "a6a5")
    with pytest.raises(IllegalMoveError):
        engine.apply_move("e5", "d6")


PROMOTION_FEN = "8/P6k/8/8/8/8/7K/8 w - - 0 1"


def test_promotion_requires_a_piece_choice() -> None:
    with pytest.raises(PromotionRequiredError):
        ChessEngine(starting_fen=PROMOTION_FEN).apply_move("a7", "a8")


@pytest.mark.parametrize(("piece", "symbol"), [("q", "Q"), ("r", "R"), ("b", "B"), ("n", "N")])
def test_promotion_to_each_piece(piece: str, symbol: str) -> None:
    engine = ChessEngine(starting_fen=PROMOTION_FEN)
    applied = engine.apply_move("a7", "a8", piece)
    assert applied.uci == f"a7a8{piece}"
    assert chess.Board(engine.fen).piece_at(chess.A8) == chess.Piece.from_symbol(symbol)


def test_promotion_to_king_or_pawn_is_rejected() -> None:
    with pytest.raises(InvalidMoveFormatError):
        ChessEngine(starting_fen=PROMOTION_FEN).apply_move("a7", "a8", "k")


def test_promotion_piece_on_ordinary_move_is_illegal() -> None:
    with pytest.raises(IllegalMoveError):
        ChessEngine().apply_move("e2", "e4", "q")


def test_check_is_detected() -> None:
    engine = play(ChessEngine(), "e2e4", "f7f6", "d2d4", "g8h6")
    applied = engine.apply_move("d1", "h5")
    assert applied.is_check and engine.is_check
    assert applied.end is None


def test_pinned_piece_cannot_expose_king() -> None:
    engine = ChessEngine(starting_fen="4r2k/8/8/8/8/8/4B3/4K3 w - - 0 1")
    with pytest.raises(IllegalMoveError):
        engine.apply_move("e2", "d3")


def test_fools_mate_is_checkmate_for_black() -> None:
    engine = play(ChessEngine(), "f2f3", "e7e5", "g2g4")
    applied = engine.apply_move("d8", "h4")
    assert applied.san == "Qh4#"
    assert applied.end is not None
    assert (applied.end.result, applied.end.reason) == (GameResult.BLACK_WIN, ResultReason.CHECKMATE)


def test_no_moves_accepted_after_checkmate() -> None:
    engine = play(ChessEngine(), "f2f3", "e7e5", "g2g4", "d8h4")
    with pytest.raises(IllegalMoveError):
        engine.apply_move("a2", "a3")


def test_stalemate_is_a_draw() -> None:
    engine = ChessEngine(starting_fen="7k/8/6K1/8/8/8/8/5Q2 w - - 0 1")
    applied = engine.apply_move("f1", "f7")
    assert applied.end is not None
    assert (applied.end.result, applied.end.reason) == (GameResult.DRAW, ResultReason.STALEMATE)


def test_insufficient_material_is_a_draw() -> None:
    engine = ChessEngine(starting_fen="7k/8/8/8/8/8/1q6/K7 w - - 0 1")
    applied = engine.apply_move("a1", "b2")  # king takes the last queen
    assert applied.end is not None
    assert applied.end.reason == ResultReason.INSUFFICIENT_MATERIAL


def test_threefold_repetition_is_a_draw() -> None:
    shuffle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    engine = play(ChessEngine(), *shuffle, *shuffle[:3])
    assert engine.detect_end() is None
    applied = engine.apply_move("f6", "g8")
    assert applied.end is not None
    assert applied.end.reason == ResultReason.THREEFOLD_REPETITION


def test_fifty_move_rule_is_a_draw() -> None:
    engine = ChessEngine(starting_fen="7k/8/8/8/8/8/R7/K7 w - - 99 80")
    applied = engine.apply_move("a2", "b2")
    assert applied.end is not None
    assert applied.end.reason == ResultReason.FIFTY_MOVE_RULE


def test_checkmate_on_the_hundredth_halfmove_beats_the_fifty_move_rule() -> None:
    engine = ChessEngine(starting_fen="7k/8/6K1/8/8/8/8/R7 w - - 99 80")
    applied = engine.apply_move("a1", "a8")
    assert applied.end is not None
    assert applied.end.reason == ResultReason.CHECKMATE


def test_replaying_history_restores_state_including_repetition_memory() -> None:
    moves = ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"]
    original = play(ChessEngine(), *moves)
    rebuilt = ChessEngine(moves)
    assert rebuilt.fen == original.fen
    assert rebuilt.san_history == original.san_history
    applied = rebuilt.apply_move("f6", "g8")
    assert applied.end is not None and applied.end.reason == ResultReason.THREEFOLD_REPETITION


def test_corrupt_history_is_detected() -> None:
    with pytest.raises(ValueError, match="corrupt"):
        ChessEngine(["e2e4", "e2e4"])


def test_can_possibly_win() -> None:
    engine = ChessEngine(starting_fen="4k3/8/8/8/8/8/3q4/4K3 w - - 0 1")
    assert engine.can_possibly_win(PlayerColor.BLACK)
    assert not engine.can_possibly_win(PlayerColor.WHITE)
