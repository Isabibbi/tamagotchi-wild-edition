
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tamagotchi_wild.domain.entities import HealthStatus, Position


class ActionType(StrEnum):
    CLAIM_TASK = "claim_task"
    ACQUIRE_AREA = "acquire_area"
    RELEASE_AREA = "release_area"
    MOVE_AGENT = "move_agent"
    MOVE_ANIMAL = "move_animal"
    UPDATE_ANIMAL_HEALTH = "update_animal_health"
    TAKE_FOOD = "take_food"
    FILL_BOWL = "fill_bowl"
    FAIL_TASK = "fail_task"
    PICKUP_SICK_ANIMAL = "pickup_sick_animal"
    DELIVER_TO_TREATMENT = "deliver_to_treatment"
    TAKE_MEDICINE = "take_medicine"
    TREAT_ANIMAL = "treat_animal"
    PICKUP_TREATED_ANIMAL = "pickup_treated_animal"
    RETURN_ANIMAL_TO_CAGE = "return_animal_to_cage"


@dataclass(frozen=True, slots=True)
class ActionCommand:
    actor_id: str
    action: ActionType
    target_id: str
    destination: Position | None = None
    health: HealthStatus | None = None
    task_id: str = ""
    quantity: int | None = None


@dataclass(frozen=True, slots=True)
class ActionResult:
    accepted: bool
    reason: str
    event_sequence: int | None = None
