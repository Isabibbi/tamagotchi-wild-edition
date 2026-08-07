"""Stato centralizzato e transizioni atomiche della griglia."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from tamagotchi_wild.domain import (
    ActionCommand,
    ActionResult,
    ActionType,
    AgentState,
    Animal,
    Area,
    Bowl,
    HealthStatus,
    Position,
    Task,
)
from tamagotchi_wild.environment.errors import (
    DuplicateEntityError,
    EnvironmentError,
    InvalidActionError,
    UnknownEntityError,
)


@dataclass(frozen=True, slots=True)
class EnvironmentEvent:
    sequence: int
    action: ActionType
    actor_id: str
    target_id: str
    origin: Position | None
    destination: Position | None
    detail: str


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    width: int
    height: int
    areas: tuple[Area, ...]
    animals: tuple[Animal, ...]
    bowls: tuple[Bowl, ...]
    agents: tuple[AgentState, ...]
    tasks: tuple[Task, ...]
    event_count: int


class EnvironmentState:
    """Single source of truth for entities, actions and events."""

    def __init__(self, width: int, height: int, areas: Iterable[Area]) -> None:
        if width < 1 or height < 1:
            raise ValueError("grid dimensions must be positive")

        area_items = tuple(areas)
        if len({area.id for area in area_items}) != len(area_items):
            raise ValueError("area identifiers must be unique")
        self.width = width
        self.height = height
        self._areas = {area.id: area for area in area_items}
        self._animals: dict[str, Animal] = {}
        self._bowls: dict[str, Bowl] = {}
        self._agents: dict[str, AgentState] = {}
        self._tasks: dict[str, Task] = {}
        self._entity_ids: set[str] = set(self._areas)
        self._events: list[EnvironmentEvent] = []
        self._validate_areas()

    @property
    def events(self) -> tuple[EnvironmentEvent, ...]:
        return tuple(self._events)

    def area_at(self, position: Position) -> Area | None:
        return next(
            (area for area in self._areas.values() if position in area.cells),
            None,
        )

    def register_animal(self, animal: Animal) -> None:
        self._register(animal.id, animal.position, self._animals, animal)

    def register_bowl(self, bowl: Bowl) -> None:
        self._register(bowl.id, bowl.position, self._bowls, bowl)

    def register_agent(self, agent: AgentState) -> None:
        self._register(agent.id, agent.position, self._agents, agent)

    def register_task(self, task: Task) -> None:
        if task.id in self._entity_ids:
            raise DuplicateEntityError(f"duplicate entity id: {task.id}")
        self._entity_ids.add(task.id)
        self._tasks[task.id] = task

    def apply(self, command: ActionCommand) -> ActionResult:
        """Validate and apply one command; rejected commands never change state."""

        try:
            event = self._apply_validated(command)
        except EnvironmentError as exc:
            return ActionResult(accepted=False, reason=str(exc))

        self._events.append(event)
        return ActionResult(
            accepted=True,
            reason="accepted",
            event_sequence=event.sequence,
        )

    def snapshot(self) -> WorldSnapshot:
        """Return an immutable projection suitable for agents, tests and GUI."""

        return WorldSnapshot(
            width=self.width,
            height=self.height,
            areas=tuple(sorted(self._areas.values(), key=lambda item: item.id)),
            animals=tuple(sorted(self._animals.values(), key=lambda item: item.id)),
            bowls=tuple(sorted(self._bowls.values(), key=lambda item: item.id)),
            agents=tuple(sorted(self._agents.values(), key=lambda item: item.id)),
            tasks=tuple(sorted(self._tasks.values(), key=lambda item: item.id)),
            event_count=len(self._events),
        )

    def _apply_validated(self, command: ActionCommand) -> EnvironmentEvent:
        if not command.actor_id.strip():
            raise InvalidActionError("actor_id must not be empty")

        if command.action is ActionType.MOVE_AGENT:
            origin = self._move_entity(
                command.target_id,
                command.destination,
                self._agents,
                "agent",
            )
            detail = "agent moved"
        elif command.action is ActionType.MOVE_ANIMAL:
            origin = self._move_entity(
                command.target_id,
                command.destination,
                self._animals,
                "animal",
            )
            detail = "animal moved"
        elif command.action is ActionType.UPDATE_ANIMAL_HEALTH:
            origin = self._update_animal_health(command.target_id, command.health)
            detail = f"health changed to {command.health.value}"
        else:
            raise InvalidActionError(f"unsupported action: {command.action}")

        return EnvironmentEvent(
            sequence=len(self._events) + 1,
            action=command.action,
            actor_id=command.actor_id,
            target_id=command.target_id,
            origin=origin,
            destination=command.destination,
            detail=detail,
        )

    def _move_entity(
        self,
        entity_id: str,
        destination: Position | None,
        entities: dict[str, AgentState] | dict[str, Animal],
        entity_type: str,
    ) -> Position:
        if destination is None:
            raise InvalidActionError("destination is required for a move")
        self._validate_position(destination)
        entity = entities.get(entity_id)
        if entity is None:
            raise UnknownEntityError(f"unknown {entity_type}: {entity_id}")

        origin = entity.position
        entities[entity_id] = replace(entity, position=destination)
        return origin

    def _update_animal_health(
        self,
        animal_id: str,
        health: HealthStatus | None,
    ) -> Position:
        if health is None:
            raise InvalidActionError("health is required for a health update")
        animal = self._animals.get(animal_id)
        if animal is None:
            raise UnknownEntityError(f"unknown animal: {animal_id}")
        self._animals[animal_id] = replace(animal, health=health)
        return animal.position

    def _register(self, entity_id, position, collection, entity) -> None:
        if entity_id in self._entity_ids:
            raise DuplicateEntityError(f"duplicate entity id: {entity_id}")
        self._validate_position(position)
        self._entity_ids.add(entity_id)
        collection[entity_id] = entity

    def _validate_position(self, position: Position) -> None:
        if not (0 <= position.x < self.width and 0 <= position.y < self.height):
            raise InvalidActionError(
                f"position ({position.x}, {position.y}) is outside the grid"
            )
        if self.area_at(position) is None:
            raise InvalidActionError(
                f"position ({position.x}, {position.y}) is not assigned to an area"
            )

    def _validate_areas(self) -> None:
        occupied: dict[Position, str] = {}
        for area in self._areas.values():
            for position in area.cells:
                if not (0 <= position.x < self.width and 0 <= position.y < self.height):
                    raise ValueError(f"area {area.id} contains a cell outside the grid")
                previous = occupied.get(position)
                if previous is not None:
                    raise ValueError(
                        f"areas {previous} and {area.id} overlap at {position}"
                    )
                occupied[position] = area.id

        expected_cells = self.width * self.height
        if len(occupied) != expected_cells:
            raise ValueError("the configured areas must cover the entire grid")
