"""Domain-level exceptions. Services raise these; API routes translate them into HTTP responses."""


class DomainError(Exception):
    """Base class for expected, user-facing business rule violations."""

    code = "domain_error"


class DuplicateAccountError(DomainError):
    """A username or email address is already registered."""


class InvalidCredentialsError(DomainError):
    """Email/password pair does not match an active account."""


class UserNotFoundError(DomainError):
    """No active player has that username."""


class GameNotFoundError(DomainError):
    """The game does not exist."""

    code = "game_not_found"


class NotAParticipantError(DomainError):
    """The user is not one of the game's players."""

    code = "not_a_participant"


class GameNotActiveError(DomainError):
    """The game has not started or has already ended."""

    code = "game_not_active"


class NotYourTurnError(DomainError):
    """A player tried to move on their opponent's turn."""

    code = "not_your_turn"


class DrawOfferError(DomainError):
    """A draw offer or response is not valid right now."""

    code = "invalid_draw_action"


class AlreadyQueuedError(DomainError):
    """The player is already waiting for a match."""


class AlreadyInGameError(DomainError):
    """The player already has an unfinished game."""


class UnsupportedTimeControlError(DomainError):
    """The requested time control is not offered."""
