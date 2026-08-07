"""Modello puro del dominio, senza dipendenze da SPADE o dalla GUI."""

from tamagotchi_wild.domain.actions import ActionCommand, ActionResult, ActionType
from tamagotchi_wild.domain.entities import (
    AgentRole,
    AgentState,
    Animal,
    Area,
    AreaType,
    Bowl,
    FoodStock,
    HealthStatus,
    MedicineStock,
    Position,
    Task,
    TaskStatus,
    TaskType,
)

__all__ = [
    "ActionCommand",
    "ActionResult",
    "ActionType",
    "AgentRole",
    "AgentState",
    "Animal",
    "Area",
    "AreaType",
    "Bowl",
    "FoodStock",
    "HealthStatus",
    "MedicineStock",
    "Position",
    "Task",
    "TaskStatus",
    "TaskType",
]
