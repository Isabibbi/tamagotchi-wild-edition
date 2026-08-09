"""Ambiente autorevole e indipendente dal trasporto XMPP."""

from tamagotchi_wild.environment.errors import (
    DuplicateEntityError,
    EnvironmentError,
    InvalidActionError,
    UnknownEntityError,
)
from tamagotchi_wild.environment.state import (
    AreaAccessState,
    EnvironmentEvent,
    EnvironmentState,
    TREATMENT_PATIENT_CAPACITY,
    WorldSnapshot,
)

__all__ = [
    "AreaAccessState",
    "DuplicateEntityError",
    "EnvironmentError",
    "EnvironmentEvent",
    "EnvironmentState",
    "InvalidActionError",
    "UnknownEntityError",
    "TREATMENT_PATIENT_CAPACITY",
    "WorldSnapshot",
]
