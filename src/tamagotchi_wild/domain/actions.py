"""Comandi e risultati accettati dall'ambiente autorevole."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tamagotchi_wild.domain.entities import HealthStatus, Position


class ActionType(StrEnum):
    MOVE_AGENT = "move_agent"
    MOVE_ANIMAL = "move_animal"
    UPDATE_ANIMAL_HEALTH = "update_animal_health"


@dataclass(frozen=True, slots=True)
class ActionCommand:
    actor_id: str
    action: ActionType
    target_id: str
    destination: Position | None = None
    health: HealthStatus | None = None


@dataclass(frozen=True, slots=True)
class ActionResult:
    accepted: bool
    reason: str
    event_sequence: int | None = None
