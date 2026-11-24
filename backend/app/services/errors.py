"""Domain-level exceptions. Services raise these; API routes translate them into HTTP responses."""


class DomainError(Exception):
    """Base class for expected, user-facing business rule violations."""


class DuplicateAccountError(DomainError):
    """A username or email address is already registered."""


class InvalidCredentialsError(DomainError):
    """Email/password pair does not match an active account."""
