"""Proiezione read-only dello stato per una futura interfaccia 2D."""

from __future__ import annotations

from dataclasses import dataclass

from tamagotchi_wild.domain import AreaType, Position
from tamagotchi_wild.environment import WorldSnapshot


@dataclass(frozen=True, slots=True)
class CellProjection:
    position: Position
    area: AreaType
    animal_ids: tuple[str, ...]
    bowl_ids: tuple[str, ...]
    agent_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GridProjection:
    width: int
    height: int
    cells: tuple[CellProjection, ...]


def project_grid(snapshot: WorldSnapshot) -> GridProjection:
    """Build render data without giving the GUI access to mutable world state."""

    area_by_cell = {
        position: area.kind
        for area in snapshot.areas
        for position in area.cells
    }
    cells = tuple(
        CellProjection(
            position=position,
            area=area_by_cell[position],
            animal_ids=tuple(
                animal.id for animal in snapshot.animals if animal.position == position
            ),
            bowl_ids=tuple(
                bowl.id for bowl in snapshot.bowls if bowl.position == position
            ),
            agent_ids=tuple(
                agent.id for agent in snapshot.agents if agent.position == position
            ),
        )
        for y in range(snapshot.height)
        for x in range(snapshot.width)
        for position in (Position(x, y),)
    )
    return GridProjection(snapshot.width, snapshot.height, cells)
