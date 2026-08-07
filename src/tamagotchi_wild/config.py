"""Configurazione non segreta della griglia iniziale."""

from __future__ import annotations

from dataclasses import dataclass

from tamagotchi_wild.domain import Area, AreaType, Position
from tamagotchi_wild.environment import EnvironmentState


@dataclass(frozen=True, slots=True)
class GridConfig:
    width: int = 12
    height: int = 8


DEFAULT_GRID = GridConfig()


def _rectangle(x_start: int, x_end: int, y_start: int, y_end: int):
    return frozenset(
        Position(x, y)
        for y in range(y_start, y_end)
        for x in range(x_start, x_end)
    )


def default_areas(config: GridConfig = DEFAULT_GRID) -> tuple[Area, ...]:
    """Partition the default grid into the four required operational areas."""

    split_x = config.width * 2 // 3
    split_y = config.height * 3 // 8
    return (
        Area(
            id="food-storage",
            kind=AreaType.FOOD_STORAGE,
            cells=_rectangle(0, split_x // 2, 0, split_y),
            capacity=2,
        ),
        Area(
            id="medical-storage",
            kind=AreaType.MEDICAL_STORAGE,
            cells=_rectangle(split_x // 2, config.width, 0, split_y),
            capacity=2,
        ),
        Area(
            id="cage-area",
            kind=AreaType.CAGE_AREA,
            cells=_rectangle(0, split_x, split_y, config.height),
            capacity=4,
        ),
        Area(
            id="treatment-room",
            kind=AreaType.TREATMENT_ROOM,
            cells=_rectangle(split_x, config.width, split_y, config.height),
            capacity=2,
        ),
    )


def create_default_environment(
    config: GridConfig = DEFAULT_GRID,
) -> EnvironmentState:
    return EnvironmentState(config.width, config.height, default_areas(config))
