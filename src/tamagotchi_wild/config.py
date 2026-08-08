"""Configurazione della griglia e della simulazione multi-agente."""

from __future__ import annotations

from dataclasses import dataclass

from tamagotchi_wild.domain import Area, AreaType, Position
from tamagotchi_wild.environment import EnvironmentState


@dataclass(frozen=True, slots=True)
class GridConfig:
    width: int = 14
    height: int = 10


DEFAULT_GRID = GridConfig()
MAX_OPERATIONAL_AGENTS = 7
MAX_ANIMALS = 40


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Numero di operatori avviati insieme; Environment non e' contato."""

    veterinary_agents: int = 2
    logistics_agents: int = 3
    feeding_agents: int = 2
    animal_count: int = 1

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
    """Crea quattro stanze e un corridoio neutro per la navigazione."""

    if config.width != 14 or config.height != 10:
        raise ValueError("the navigable CRAS layout requires a 14x10 grid")
    return (
        Area(
            id="corridor",
            kind=AreaType.CORRIDOR,
            cells=(
                _rectangle(0, 14, 4, 5)
                | _rectangle(5, 6, 0, 4)
                | _rectangle(9, 10, 5, 10)
            ),
            capacity=7,
        ),
        Area(
            id="food-storage",
            kind=AreaType.FOOD_STORAGE,
            cells=_rectangle(0, 5, 0, 4),
            capacity=2,
        ),
        Area(
            id="medical-storage",
            kind=AreaType.MEDICAL_STORAGE,
            cells=_rectangle(6, 14, 0, 4),
            capacity=2,
        ),
        Area(
            id="cage-area",
            kind=AreaType.CAGE_AREA,
            cells=_rectangle(0, 9, 5, 10),
            capacity=2,
        ),
        Area(
            id="treatment-room",
            kind=AreaType.TREATMENT_ROOM,
            cells=_rectangle(10, 14, 5, 10),
            capacity=2,
        ),
    )


def create_default_environment(
    config: GridConfig = DEFAULT_GRID,
) -> EnvironmentState:
    return EnvironmentState(config.width, config.height, default_areas(config))
