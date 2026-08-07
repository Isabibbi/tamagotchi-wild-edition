"""Ambiente autorevole e indipendente dal trasporto XMPP."""

from tamagotchi_wild.environment.errors import (
    DuplicateEntityError,
    EnvironmentError,
    InvalidActionError,
    UnknownEntityError,
)
from tamagotchi_wild.environment.state import (
    EnvironmentEvent,
    EnvironmentState,
    WorldSnapshot,
)

__all__ = [
    "DuplicateEntityError",
    "EnvironmentError",
    "EnvironmentEvent",
    "EnvironmentState",
    "InvalidActionError",
    "UnknownEntityError",
    "WorldSnapshot",
]
