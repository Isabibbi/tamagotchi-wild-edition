
from __future__ import annotations

from dataclasses import dataclass

from tamagotchi_wild.domain import Area, AreaType, Position
from tamagotchi_wild.environment import EnvironmentState


@dataclass(frozen=True, slots=True)
class GridConfig:
    width: int = 12
    height: int = 8


DEFAULT_GRID = GridConfig()
MAX_OPERATIONAL_AGENTS = 15
MAX_ANIMALS = 40


@dataclass(frozen=True, slots=True)
class SimulationConfig:

    veterinary_agents: int = 2
    logistics_agents: int = 3
    feeding_agents: int = 2
    animal_count: int = 5

    def __post_init__(self) -> None:
        counts = {
            "veterinary_agents": self.veterinary_agents,
            "logistics_agents": self.logistics_agents,
            "feeding_agents": self.feeding_agents,
        }
        for name, value in counts.items():
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.operator_count > MAX_OPERATIONAL_AGENTS:
            raise ValueError(
                f"at most {MAX_OPERATIONAL_AGENTS} operational agents are allowed"
            )
        if type(self.animal_count) is not int or not 1 <= self.animal_count <= MAX_ANIMALS:
            raise ValueError(f"animal_count must be between 1 and {MAX_ANIMALS}")

    @property
    def operator_count(self) -> int:
        return (
            self.veterinary_agents
            + self.logistics_agents
            + self.feeding_agents
        )

    @staticmethod
    def jids(role: str, count: int) -> tuple[str, ...]:
        return tuple(f"{role}_{index:02d}@localhost" for index in range(1, count + 1))


def _rectangle(x_start: int, x_end: int, y_start: int, y_end: int):
    return frozenset(
        Position(x, y)
        for y in range(y_start, y_end)
        for x in range(x_start, x_end)
    )


def default_areas(config: GridConfig = DEFAULT_GRID) -> tuple[Area, ...]:
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
            capacity=2,
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
