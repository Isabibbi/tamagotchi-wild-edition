"""Stato centralizzato e transizioni atomiche della griglia."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from tamagotchi_wild.domain import (
    ActionCommand,
    ActionResult,
    ActionType,
    AgentRole,
    AgentState,
    Animal,
    Area,
    AreaType,
    Bowl,
    Cage,
    FoodStock,
    HealthStatus,
    MedicineStock,
    Position,
    Task,
    TaskStatus,
    TaskType,
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
    task_id: str = ""
    quantity: int | None = None


@dataclass(frozen=True, slots=True)
class AreaAccessState:
    area_id: str
    capacity: int
    occupants: tuple[str, ...]
    max_observed: int


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    width: int
    height: int
    areas: tuple[Area, ...]
    animals: tuple[Animal, ...]
    bowls: tuple[Bowl, ...]
    cages: tuple[Cage, ...]
    food_stocks: tuple[FoodStock, ...]
    medicine_stocks: tuple[MedicineStock, ...]
    agents: tuple[AgentState, ...]
    tasks: tuple[Task, ...]
    area_access: tuple[AreaAccessState, ...]
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
        self._cages: dict[str, Cage] = {}
        self._food_stocks: dict[str, FoodStock] = {}
        self._medicine_stocks: dict[str, MedicineStock] = {}
        self._agents: dict[str, AgentState] = {}
        self._tasks: dict[str, Task] = {}
        self._entity_ids: set[str] = set(self._areas)
        self._events: list[EnvironmentEvent] = []
        self._applied_task_actions: dict[tuple[str, ActionType], ActionResult] = {}
        self._task_claims: dict[tuple[str, str], str] = {}
        self._area_occupants: dict[str, set[str]] = {
            area_id: set() for area_id in self._areas
        }
        self._agent_area_access: dict[str, str] = {}
        self._agent_area_task: dict[str, str] = {}
        self._max_area_occupancy: dict[str, int] = {
            area_id: 0 for area_id in self._areas
        }
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

    def register_cage(self, cage: Cage) -> None:
        self._register(cage.id, cage.position, self._cages, cage)

    def register_food_stock(self, food_stock: FoodStock) -> None:
        self._register(
            food_stock.id,
            food_stock.position,
            self._food_stocks,
            food_stock,
        )

    def register_medicine_stock(self, medicine_stock: MedicineStock) -> None:
        self._register(
            medicine_stock.id,
            medicine_stock.position,
            self._medicine_stocks,
            medicine_stock,
        )

    def register_agent(self, agent: AgentState) -> None:
        self._register(agent.id, agent.position, self._agents, agent)

    def register_task(self, task: Task) -> None:
        if task.id in self._entity_ids:
            raise DuplicateEntityError(f"duplicate entity id: {task.id}")
        self._entity_ids.add(task.id)
        self._tasks[task.id] = task

    def apply(self, command: ActionCommand) -> ActionResult:
        """Validate and apply one command; rejected commands never change state."""

        if command.action is ActionType.CLAIM_TASK:
            return self._apply_task_claim(command)
        if command.action is ActionType.ACQUIRE_AREA:
            return self._apply_area_acquire(command)
        if command.action is ActionType.RELEASE_AREA:
            return self._apply_area_release(command)

        idempotency_key = self._idempotency_key(command)
        if idempotency_key is not None:
            previous = self._applied_task_actions.get(idempotency_key)
            if previous is not None:
                return ActionResult(
                    accepted=True,
                    reason="already_applied",
                    event_sequence=previous.event_sequence,
                )

        try:
            event = self._apply_validated(command)
        except EnvironmentError as exc:
            return ActionResult(accepted=False, reason=str(exc))

        self._events.append(event)
        result = ActionResult(
            accepted=True,
            reason="accepted",
            event_sequence=event.sequence,
        )
        if idempotency_key is not None:
            self._applied_task_actions[idempotency_key] = result
        return result

    def snapshot(self) -> WorldSnapshot:
        """Return an immutable projection suitable for agents, tests and GUI."""

        return WorldSnapshot(
            width=self.width,
            height=self.height,
            areas=tuple(sorted(self._areas.values(), key=lambda item: item.id)),
            animals=tuple(sorted(self._animals.values(), key=lambda item: item.id)),
            bowls=tuple(sorted(self._bowls.values(), key=lambda item: item.id)),
            cages=tuple(sorted(self._cages.values(), key=lambda item: item.id)),
            food_stocks=tuple(
                sorted(self._food_stocks.values(), key=lambda item: item.id)
            ),
            medicine_stocks=tuple(
                sorted(self._medicine_stocks.values(), key=lambda item: item.id)
            ),
            agents=tuple(sorted(self._agents.values(), key=lambda item: item.id)),
            tasks=tuple(sorted(self._tasks.values(), key=lambda item: item.id)),
            area_access=tuple(
                AreaAccessState(
                    area_id=area_id,
                    capacity=min(area.capacity, 2),
                    occupants=tuple(sorted(self._area_occupants[area_id])),
                    max_observed=self._max_area_occupancy[area_id],
                )
                for area_id, area in sorted(self._areas.items())
            ),
            event_count=len(self._events),
        )

    def _apply_task_claim(self, command: ActionCommand) -> ActionResult:
        try:
            task = self._task(command.task_id)
            actor = self._agents.get(command.actor_id)
            if actor is None:
                raise UnknownEntityError(f"unknown agent: {command.actor_id}")
            expected_role = {
                "feeding_coordination": AgentRole.LOGISTICS,
                "feeding_execution": AgentRole.FEEDING,
                "medical_coordination": AgentRole.VETERINARY,
                "transport_outbound": AgentRole.LOGISTICS,
                "transport_return": AgentRole.LOGISTICS,
            }.get(command.target_id)
            if expected_role is None:
                raise InvalidActionError(f"unknown task phase: {command.target_id}")
            if actor.role is not expected_role:
                raise InvalidActionError(
                    f"agent {actor.id} cannot claim phase {command.target_id}"
                )
            if command.target_id.startswith("feeding") and task.kind is not TaskType.REFILL_BOWL:
                raise InvalidActionError(f"task {task.id} is not a feeding task")
            if command.target_id.startswith(("medical", "transport")) and task.kind is not TaskType.TREAT_ANIMAL:
                raise InvalidActionError(f"task {task.id} is not a medical task")
        except EnvironmentError as exc:
            return ActionResult(False, str(exc))

        key = (task.id, command.target_id)
        owner = self._task_claims.get(key)
        if owner is not None:
            if owner == command.actor_id:
                return ActionResult(True, "already_claimed")
            return ActionResult(False, f"task phase already claimed by {owner}")

        self._task_claims[key] = command.actor_id
        if command.target_id in {"feeding_execution", "medical_coordination"}:
            self._tasks[task.id] = replace(
                task,
                status=TaskStatus.ASSIGNED,
                assigned_to=command.actor_id,
            )
        event = self._append_event(command, actor.position, "task phase claimed")
        return ActionResult(True, "accepted", event.sequence)

    def _apply_area_acquire(self, command: ActionCommand) -> ActionResult:
        try:
            actor = self._agents.get(command.actor_id)
            if actor is None:
                raise UnknownEntityError(f"unknown agent: {command.actor_id}")
            area = self._areas.get(command.target_id)
            if area is None:
                raise UnknownEntityError(f"unknown area: {command.target_id}")
            current = self._agent_area_access.get(actor.id)
            current_task = self._agent_area_task.get(actor.id)
            if current == area.id and current_task == command.task_id:
                return ActionResult(True, "already_acquired")
            if current is not None:
                raise InvalidActionError(
                    f"agent {actor.id} is busy with task {current_task} in area {current}"
                )
            occupants = self._area_occupants[area.id]
            capacity = min(area.capacity, 2)
            if len(occupants) >= capacity:
                raise InvalidActionError(f"area {area.id} is at capacity")
            destination = command.destination or actor.position
            self._validate_position(destination)
            if destination not in area.cells:
                raise InvalidActionError(f"destination must be in area {area.id}")
        except EnvironmentError as exc:
            return ActionResult(False, str(exc))

        origin = actor.position
        occupants.add(actor.id)
        self._agent_area_access[actor.id] = area.id
        self._agent_area_task[actor.id] = command.task_id
        self._agents[actor.id] = replace(actor, position=destination)
        self._max_area_occupancy[area.id] = max(
            self._max_area_occupancy[area.id],
            len(occupants),
        )
        event = self._append_event(command, origin, "area acquired")
        return ActionResult(True, "accepted", event.sequence)

    def _apply_area_release(self, command: ActionCommand) -> ActionResult:
        try:
            actor = self._agents.get(command.actor_id)
            if actor is None:
                raise UnknownEntityError(f"unknown agent: {command.actor_id}")
            if command.target_id not in self._areas:
                raise UnknownEntityError(f"unknown area: {command.target_id}")
            current = self._agent_area_access.get(actor.id)
            current_task = self._agent_area_task.get(actor.id)
            if current is None:
                return ActionResult(True, "already_released")
            if current != command.target_id:
                raise InvalidActionError(f"agent {actor.id} does not hold area {command.target_id}")
            if current_task != command.task_id:
                raise InvalidActionError(
                    f"area {command.target_id} is held for task {current_task}"
                )
        except EnvironmentError as exc:
            return ActionResult(False, str(exc))

        self._area_occupants[command.target_id].remove(actor.id)
        del self._agent_area_access[actor.id]
        del self._agent_area_task[actor.id]
        event = self._append_event(command, actor.position, "area released")
        return ActionResult(True, "accepted", event.sequence)

    def _append_event(
        self,
        command: ActionCommand,
        origin: Position | None,
        detail: str,
    ) -> EnvironmentEvent:
        event = EnvironmentEvent(
            sequence=len(self._events) + 1,
            action=command.action,
            actor_id=command.actor_id,
            target_id=command.target_id,
            origin=origin,
            destination=command.destination,
            detail=detail,
            task_id=command.task_id,
            quantity=command.quantity,
        )
        self._events.append(event)
        return event

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
        elif command.action is ActionType.TAKE_FOOD:
            origin = self._take_food(command)
            detail = "food taken"
        elif command.action is ActionType.FILL_BOWL:
            origin = self._fill_bowl(command)
            detail = "bowl filled"
        elif command.action is ActionType.FAIL_TASK:
            origin = self._fail_task(command)
            detail = "task rejected"
        elif command.action is ActionType.PICKUP_SICK_ANIMAL:
            origin = self._pickup_sick_animal(command)
            detail = "sick animal picked up"
        elif command.action is ActionType.DELIVER_TO_TREATMENT:
            origin = self._deliver_to_treatment(command)
            detail = "animal delivered to treatment"
        elif command.action is ActionType.TAKE_MEDICINE:
            origin = self._take_medicine(command)
            detail = "medicine taken"
        elif command.action is ActionType.TREAT_ANIMAL:
            origin = self._treat_animal(command)
            detail = "animal treated"
        elif command.action is ActionType.PICKUP_TREATED_ANIMAL:
            origin = self._pickup_treated_animal(command)
            detail = "treated animal picked up"
        elif command.action is ActionType.RETURN_ANIMAL_TO_CAGE:
            origin = self._return_animal_to_cage(command)
            detail = "animal returned to cage"
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
            task_id=command.task_id,
            quantity=command.quantity,
        )

    def _take_food(self, command: ActionCommand) -> Position:
        task = self._feeding_task(command.task_id)
        self._actor(command.actor_id, AgentRole.FEEDING)
        self._require_area_access(command.actor_id, AreaType.FOOD_STORAGE)
        food_stock = self._food_stocks.get(command.target_id)
        if food_stock is None:
            raise UnknownEntityError(f"unknown food stock: {command.target_id}")
        quantity = self._feeding_quantity(command.quantity)
        if food_stock.quantity < quantity:
            raise InvalidActionError("not enough food")
        if task.status is TaskStatus.COMPLETED:
            raise InvalidActionError(f"task {task.id} is already completed")

        self._food_stocks[food_stock.id] = replace(
            food_stock,
            quantity=food_stock.quantity - quantity,
        )
        self._tasks[task.id] = replace(
            task,
            status=TaskStatus.IN_PROGRESS,
            assigned_to=command.actor_id,
        )
        return food_stock.position

    def _fill_bowl(self, command: ActionCommand) -> Position:
        task = self._feeding_task(command.task_id)
        self._actor(command.actor_id, AgentRole.FEEDING)
        self._require_area_access(command.actor_id, AreaType.CAGE_AREA)
        bowl = self._bowls.get(command.target_id)
        if bowl is None:
            raise UnknownEntityError(f"unknown bowl: {command.target_id}")
        if task.target_id != bowl.id:
            raise InvalidActionError(
                f"task {task.id} targets {task.target_id}, not {bowl.id}"
            )
        if (task.id, ActionType.TAKE_FOOD) not in self._applied_task_actions:
            raise InvalidActionError(f"food has not been taken for task {task.id}")
        quantity = self._feeding_quantity(command.quantity)
        if bowl.level + quantity > bowl.capacity:
            raise InvalidActionError(f"bowl {bowl.id} does not have enough capacity")

        self._bowls[bowl.id] = replace(bowl, level=bowl.level + quantity)
        self._tasks[task.id] = replace(task, status=TaskStatus.COMPLETED)
        return bowl.position

    def _feeding_task(self, task_id: str) -> Task:
        task = self._task(task_id)
        if task.kind is not TaskType.REFILL_BOWL:
            raise InvalidActionError(f"task {task_id} is not a feeding task")
        return task

    def _medical_task(self, task_id: str) -> Task:
        task = self._task(task_id)
        if task.kind is not TaskType.TREAT_ANIMAL:
            raise InvalidActionError(f"task {task_id} is not a medical task")
        return task

    def _task(self, task_id: str) -> Task:
        if not task_id.strip():
            raise InvalidActionError("task_id is required")
        task = self._tasks.get(task_id)
        if task is None:
            raise UnknownEntityError(f"unknown task: {task_id}")
        return task

    def _fail_task(self, command: ActionCommand) -> None:
        task = self._task(command.task_id)
        if command.target_id != task.id:
            raise InvalidActionError(
                f"fail_task target must be task {task.id}, not {command.target_id}"
            )
        if task.status is TaskStatus.COMPLETED:
            raise InvalidActionError(f"completed task {task.id} cannot be rejected")
        self._tasks[task.id] = replace(
            task,
            status=TaskStatus.REJECTED,
            assigned_to=command.actor_id,
        )
        return None

    def _pickup_sick_animal(self, command: ActionCommand) -> Position:
        task = self._medical_task(command.task_id)
        logistics = self._actor(command.actor_id, AgentRole.LOGISTICS)
        self._require_area_access(command.actor_id, AreaType.CAGE_AREA)
        animal = self._medical_animal(task, command.target_id)
        if animal.health is not HealthStatus.SICK:
            raise InvalidActionError(f"animal {animal.id} is not sick in its cage")
        self._require_area(animal.position, AreaType.CAGE_AREA, "animal")
        self._require_area(logistics.position, AreaType.CAGE_AREA, "logistics agent")

        self._animals[animal.id] = replace(
            animal,
            health=HealthStatus.IN_OUTBOUND_TRANSPORT,
            carried_by=command.actor_id,
        )
        self._tasks[task.id] = replace(
            task,
            status=TaskStatus.IN_PROGRESS,
            assigned_to=command.actor_id,
        )
        return animal.position

    def _deliver_to_treatment(self, command: ActionCommand) -> Position:
        task = self._medical_task(command.task_id)
        logistics = self._actor(command.actor_id, AgentRole.LOGISTICS)
        self._require_area_access(command.actor_id, AreaType.TREATMENT_ROOM)
        animal = self._medical_animal(task, command.target_id)
        if animal.health is not HealthStatus.IN_OUTBOUND_TRANSPORT:
            raise InvalidActionError(f"animal {animal.id} is not in outbound transport")
        if animal.carried_by != command.actor_id:
            raise InvalidActionError(f"animal {animal.id} is not carried by {command.actor_id}")
        destination = self._medical_destination(
            command.destination,
            AreaType.TREATMENT_ROOM,
        )

        self._animals[animal.id] = replace(
            animal,
            position=destination,
            health=HealthStatus.IN_TREATMENT,
            carried_by=None,
        )
        self._agents[logistics.id] = replace(logistics, position=destination)
        return animal.position

    def _take_medicine(self, command: ActionCommand) -> Position:
        task = self._medical_task(command.task_id)
        veterinary = self._actor(command.actor_id, AgentRole.VETERINARY)
        self._require_area_access(command.actor_id, AreaType.MEDICAL_STORAGE)
        animal = self._medical_animal(task, task.target_id)
        if animal.health is not HealthStatus.IN_TREATMENT:
            raise InvalidActionError(f"animal {animal.id} is not ready for treatment")
        medicine = self._medicine_stocks.get(command.target_id)
        if medicine is None:
            raise UnknownEntityError(f"unknown medicine stock: {command.target_id}")
        quantity = self._feeding_quantity(command.quantity)
        if medicine.quantity < quantity:
            raise InvalidActionError("not enough medicine")
        self._require_area(medicine.position, AreaType.MEDICAL_STORAGE, "medicine stock")

        self._medicine_stocks[medicine.id] = replace(
            medicine,
            quantity=medicine.quantity - quantity,
        )
        self._agents[veterinary.id] = replace(veterinary, position=medicine.position)
        self._tasks[task.id] = replace(
            task,
            status=TaskStatus.IN_PROGRESS,
            assigned_to=command.actor_id,
        )
        return medicine.position

    def _treat_animal(self, command: ActionCommand) -> Position:
        task = self._medical_task(command.task_id)
        veterinary = self._actor(command.actor_id, AgentRole.VETERINARY)
        self._require_area_access(command.actor_id, AreaType.TREATMENT_ROOM)
        animal = self._medical_animal(task, command.target_id)
        if animal.health is not HealthStatus.IN_TREATMENT:
            raise InvalidActionError(f"animal {animal.id} is not in treatment")
        if (task.id, ActionType.TAKE_MEDICINE) not in self._applied_task_actions:
            raise InvalidActionError(
                f"medicine has not been taken for task {task.id}"
            )
        self._require_area(veterinary.position, AreaType.TREATMENT_ROOM, "veterinary")
        if veterinary.position != animal.position:
            raise InvalidActionError("veterinary and animal are not in the same cell")

        self._animals[animal.id] = replace(animal, health=HealthStatus.TREATED)
        return animal.position

    def _pickup_treated_animal(self, command: ActionCommand) -> Position:
        task = self._medical_task(command.task_id)
        logistics = self._actor(command.actor_id, AgentRole.LOGISTICS)
        self._require_area_access(command.actor_id, AreaType.TREATMENT_ROOM)
        animal = self._medical_animal(task, command.target_id)
        if animal.health is not HealthStatus.TREATED:
            raise InvalidActionError(f"animal {animal.id} has not been treated")
        if logistics.position != animal.position:
            raise InvalidActionError("logistics agent and animal are not in the same cell")

        self._animals[animal.id] = replace(
            animal,
            health=HealthStatus.IN_RETURN_TRANSPORT,
            carried_by=command.actor_id,
        )
        self._tasks[task.id] = replace(task, assigned_to=command.actor_id)
        return animal.position

    def _return_animal_to_cage(self, command: ActionCommand) -> Position:
        task = self._medical_task(command.task_id)
        logistics = self._actor(command.actor_id, AgentRole.LOGISTICS)
        self._require_area_access(command.actor_id, AreaType.CAGE_AREA)
        animal = self._medical_animal(task, command.target_id)
        if animal.health is not HealthStatus.IN_RETURN_TRANSPORT:
            raise InvalidActionError(f"animal {animal.id} is not in return transport")
        if animal.carried_by != command.actor_id:
            raise InvalidActionError(f"animal {animal.id} is not carried by {command.actor_id}")
        destination = self._medical_destination(command.destination, AreaType.CAGE_AREA)

        self._animals[animal.id] = replace(
            animal,
            position=destination,
            health=HealthStatus.HEALTHY,
            carried_by=None,
        )
        self._agents[logistics.id] = replace(logistics, position=destination)
        self._tasks[task.id] = replace(task, status=TaskStatus.COMPLETED)
        return animal.position

    def _medical_animal(self, task: Task, animal_id: str) -> Animal:
        if task.target_id != animal_id:
            raise InvalidActionError(
                f"task {task.id} targets {task.target_id}, not {animal_id}"
            )
        animal = self._animals.get(animal_id)
        if animal is None:
            raise UnknownEntityError(f"unknown animal: {animal_id}")
        return animal

    def _actor(self, actor_id: str, role: AgentRole) -> AgentState:
        actor = self._agents.get(actor_id)
        if actor is None:
            raise UnknownEntityError(f"unknown agent: {actor_id}")
        if actor.role is not role:
            raise InvalidActionError(f"agent {actor_id} does not have role {role.value}")
        return actor

    def _medical_destination(
        self,
        destination: Position | None,
        area_type: AreaType,
    ) -> Position:
        if destination is None:
            raise InvalidActionError("destination is required")
        self._validate_position(destination)
        self._require_area(destination, area_type, "destination")
        return destination

    def _require_area(
        self,
        position: Position,
        expected: AreaType,
        subject: str,
    ) -> None:
        area = self.area_at(position)
        if area is None or area.kind is not expected:
            raise InvalidActionError(f"{subject} must be in {expected.value}")

    def _require_area_access(self, actor_id: str, expected: AreaType) -> None:
        area_id = self._agent_area_access.get(actor_id)
        area = self._areas.get(area_id) if area_id is not None else None
        if area is None or area.kind is not expected:
            raise InvalidActionError(
                f"agent {actor_id} must acquire {expected.value} before acting"
            )

    @staticmethod
    def _feeding_quantity(quantity: int | None) -> int:
        if type(quantity) is not int or quantity < 1:
            raise InvalidActionError("quantity must be a positive integer")
        return quantity

    @staticmethod
    def _idempotency_key(
        command: ActionCommand,
    ) -> tuple[str, ActionType] | None:
        if command.action not in (
            ActionType.TAKE_FOOD,
            ActionType.FILL_BOWL,
            ActionType.PICKUP_SICK_ANIMAL,
            ActionType.DELIVER_TO_TREATMENT,
            ActionType.TAKE_MEDICINE,
            ActionType.TREAT_ANIMAL,
            ActionType.PICKUP_TREATED_ANIMAL,
            ActionType.RETURN_ANIMAL_TO_CAGE,
        ):
            return None
        if not command.task_id.strip():
            return None
        return command.task_id, command.action

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
