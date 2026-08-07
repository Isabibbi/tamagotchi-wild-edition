"""Errori di validazione dell'ambiente."""


class EnvironmentError(Exception):
    """Base error for rejected environment operations."""


class DuplicateEntityError(EnvironmentError):
    """Raised when an identifier is already present in the world."""


class UnknownEntityError(EnvironmentError):
    """Raised when an operation targets an unknown entity."""


class InvalidActionError(EnvironmentError):
    """Raised when an action violates a world precondition."""
