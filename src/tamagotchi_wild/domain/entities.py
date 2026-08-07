"""Entità e valori del dominio del centro di recupero."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


def _require_identifier(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True, order=True)
class Position:
    """Coordinata immutabile nella griglia 2D."""

    x: int
    y: int

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int:
            raise TypeError("position coordinates must be integers")


class AreaType(StrEnum):
    FOOD_STORAGE = "food_storage"
    MEDICAL_STORAGE = "medical_storage"
    CAGE_AREA = "cage_area"
    TREATMENT_ROOM = "treatment_room"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    HUNGRY = "hungry"
    SICK = "sick"
    IN_TREATMENT = "in_treatment"
    READY_FOR_TRANSPORT = "ready_for_transport"
    IN_OUTBOUND_TRANSPORT = "in_outbound_transport"
    TREATED = "treated"
    IN_RETURN_TRANSPORT = "in_return_transport"


class AgentRole(StrEnum):
    VETERINARY = "veterinary"
    FEEDING = "feeding"
    LOGISTICS = "logistics"


class TaskType(StrEnum):
    REFILL_BOWL = "refill_bowl"
    TRANSPORT_ANIMAL = "transport_animal"
    TREAT_ANIMAL = "treat_animal"


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Area:
    id: str
    kind: AreaType
    cells: frozenset[Position]
    capacity: int

    def __post_init__(self) -> None:
        _require_identifier(self.id, "area id")
        object.__setattr__(self, "cells", frozenset(self.cells))
        if not self.cells:
            raise ValueError("an area must contain at least one cell")
        if self.capacity < 1:
            raise ValueError("area capacity must be positive")


@dataclass(frozen=True, slots=True)
class Animal:
    id: str
    species: str
    position: Position
    health: HealthStatus = HealthStatus.HEALTHY
    carried_by: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.id, "animal id")
        _require_identifier(self.species, "animal species")


@dataclass(frozen=True, slots=True)
class Bowl:
    id: str
    cage_id: str
    position: Position
    level: int = 0
    capacity: int = 1

    def __post_init__(self) -> None:
        _require_identifier(self.id, "bowl id")
        _require_identifier(self.cage_id, "cage id")
        if self.capacity < 1:
            raise ValueError("bowl capacity must be positive")
        if not 0 <= self.level <= self.capacity:
            raise ValueError("bowl level must be between zero and capacity")


@dataclass(frozen=True, slots=True)
class FoodStock:
    id: str
    position: Position
    quantity: int

    def __post_init__(self) -> None:
        _require_identifier(self.id, "food stock id")
        if self.quantity < 0:
            raise ValueError("food quantity must not be negative")


@dataclass(frozen=True, slots=True)
class MedicineStock:
    id: str
    position: Position
    quantity: int

    def __post_init__(self) -> None:
        _require_identifier(self.id, "medicine stock id")
        if self.quantity < 0:
            raise ValueError("medicine quantity must not be negative")


@dataclass(frozen=True, slots=True)
class AgentState:
    id: str
    role: AgentRole
    position: Position
    current_task_id: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.id, "agent id")


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    kind: TaskType
    target_id: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.id, "task id")
        _require_identifier(self.target_id, "task target id")
