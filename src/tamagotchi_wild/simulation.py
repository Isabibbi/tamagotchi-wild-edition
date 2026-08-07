"""Simulazione unica: alimentazione e cure mediche procedono insieme."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json

import spade

from tamagotchi_wild.agents import (
    EnvironmentAgent,
    FeedingAgent,
    LogisticsAgent,
    VeterinaryAgent,
)
from tamagotchi_wild.config import SimulationConfig, create_default_environment
from tamagotchi_wild.domain import (
    AgentRole,
    AgentState,
    Animal,
    Bowl,
    FoodStock,
    HealthStatus,
    MedicineStock,
    Position,
    Task,
    TaskStatus,
    TaskType,
)
from tamagotchi_wild.environment import EnvironmentState
from tamagotchi_wild.observability import ActivityLog, MessageTrace


PASSWORD = "local-cras-password"
ENVIRONMENT_JID = "environment@localhost"
FEEDING_TASK_ID = "feeding_001"
MEDICAL_TASK_ID = "medical_001"
CAGE_ID = "cage_01"
BOWL_ID = "bowl_01"
FOOD_STOCK_ID = "food_stock_01"
ANIMAL_ID = "animal_001"
MEDICINE_STOCK_ID = "medicine_stock_01"
FOOD_POSITION = Position(1, 1)
MEDICINE_POSITION = Position(6, 1)
CAGE_POSITION = Position(2, 4)
TREATMENT_POSITION = Position(9, 4)


@dataclass(frozen=True, slots=True)
class SimulationResult:
    success: bool
    operator_count: int
    spade_agent_count: int
    veterinary_agents: int
    logistics_agents: int
    feeding_agents: int
    feeding_status: str
    medical_status: str
    bowl_level: int
    food_remaining: int
    animal_health: str
    medicine_remaining: int
    max_room_occupancy: int
    room_capacity: int
    active_room_occupancy_at_end: int
    task_claims: tuple[str, ...]
    message_count: int
    conversation_ids: tuple[str, ...]
    logs: tuple[str, ...]
    error: str | None = None


def build_environment(config: SimulationConfig, food: int, medicine: int) -> EnvironmentState:
    world = create_default_environment()
    world.register_bowl(Bowl(BOWL_ID, CAGE_ID, CAGE_POSITION))
    world.register_food_stock(FoodStock(FOOD_STOCK_ID, FOOD_POSITION, food))
    world.register_animal(Animal(ANIMAL_ID, "fox", CAGE_POSITION, HealthStatus.SICK))
    world.register_medicine_stock(
        MedicineStock(MEDICINE_STOCK_ID, MEDICINE_POSITION, medicine)
    )
    world.register_task(Task(FEEDING_TASK_ID, TaskType.REFILL_BOWL, BOWL_ID))
    world.register_task(Task(MEDICAL_TASK_ID, TaskType.TREAT_ANIMAL, ANIMAL_ID))

    identities = (
        *((jid, AgentRole.VETERINARY) for jid in config.jids("veterinary", config.veterinary_agents)),
        *((jid, AgentRole.LOGISTICS) for jid in config.jids("logistics", config.logistics_agents)),
        *((jid, AgentRole.FEEDING) for jid in config.jids("feeding", config.feeding_agents)),
    )
    staging_positions = (
        Position(1, 1),
        Position(5, 1),
        Position(2, 4),
        Position(9, 4),
        Position(2, 1),
        Position(6, 1),
        Position(3, 4),
    )
    for (jid, role), position in zip(
        identities,
        staging_positions[: len(identities)],
        strict=True,
    ):
        world.register_agent(AgentState(jid.split("@", 1)[0], role, position))
    return world


async def _wait_until_one_finishes(agents, timeout_seconds: float) -> None:
    async def wait() -> None:
        while not any(agent.workflow_done.is_set() for agent in agents):
            await asyncio.sleep(0.05)

    await asyncio.wait_for(wait(), timeout=timeout_seconds)


async def execute_simulation(
    config: SimulationConfig = SimulationConfig(),
    food: int = 2,
    medicine: int = 1,
    timeout_seconds: float = 30.0,
) -> SimulationResult:
    world = build_environment(config, food, medicine)
    activity_log = ActivityLog()
    message_trace = MessageTrace()
    feeding_jids = config.jids("feeding", config.feeding_agents)
    logistics_jids = config.jids("logistics", config.logistics_agents)
    veterinary_jids = config.jids("veterinary", config.veterinary_agents)

    environment = EnvironmentAgent(
        ENVIRONMENT_JID,
        PASSWORD,
        world,
        activity_log,
        message_trace,
    )
    feeding_agents = [
        FeedingAgent(
            jid,
            PASSWORD,
            ENVIRONMENT_JID,
            FOOD_STOCK_ID,
            activity_log,
            message_trace,
            timeout_seconds,
            food_position=FOOD_POSITION,
            bowl_position=CAGE_POSITION,
        )
        for jid in feeding_jids
    ]
    logistics_agents = [
        LogisticsAgent(
            jid,
            PASSWORD,
            feeding_jids,
            activity_log,
            message_trace,
            timeout_seconds,
            environment_jid=ENVIRONMENT_JID,
            cage_position=CAGE_POSITION,
            treatment_position=TREATMENT_POSITION,
        )
        for jid in logistics_jids
    ]
    veterinary_agents = [
        VeterinaryAgent(
            jid,
            PASSWORD,
            logistics_jids,
            ENVIRONMENT_JID,
            MEDICINE_STOCK_ID,
            TREATMENT_POSITION,
            activity_log,
            message_trace,
            timeout_seconds,
            medicine_position=MEDICINE_POSITION,
        )
        for jid in veterinary_jids
    ]
    operators = [*feeding_agents, *logistics_agents, *veterinary_agents]
    started = []
    error: str | None = None

    try:
        await environment.start(auto_register=True)
        started.append(environment)
        for agent in operators:
            await agent.start(auto_register=True)
            started.append(agent)
        await asyncio.wait_for(
            asyncio.gather(*(agent.bdi_ready.wait() for agent in operators)),
            timeout=timeout_seconds,
        )

        await asyncio.gather(
            *(
                environment.publish_bowl_empty(
                    jid,
                    FEEDING_TASK_ID,
                    CAGE_ID,
                    BOWL_ID,
                )
                for jid in logistics_jids
            ),
            *(
                environment.publish_sick_animal(
                    jid,
                    MEDICAL_TASK_ID,
                    ANIMAL_ID,
                    CAGE_ID,
                )
                for jid in veterinary_jids
            ),
        )
        await asyncio.gather(
            _wait_until_one_finishes(logistics_agents, timeout_seconds),
            _wait_until_one_finishes(veterinary_agents, timeout_seconds),
        )
    except TimeoutError:
        error = f"integrated simulation timed out after {timeout_seconds:g} seconds"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        for agent in reversed(started):
            await agent.stop()

    snapshot = world.snapshot()
    bowl = next(item for item in snapshot.bowls if item.id == BOWL_ID)
    stock = next(item for item in snapshot.food_stocks if item.id == FOOD_STOCK_ID)
    animal = next(item for item in snapshot.animals if item.id == ANIMAL_ID)
    medicine_stock = next(
        item for item in snapshot.medicine_stocks if item.id == MEDICINE_STOCK_ID
    )
    feeding_task = next(item for item in snapshot.tasks if item.id == FEEDING_TASK_ID)
    medical_task = next(item for item in snapshot.tasks if item.id == MEDICAL_TASK_ID)
    max_occupancy = max(item.max_observed for item in snapshot.area_access)
    active_occupancy = sum(len(item.occupants) for item in snapshot.area_access)
    claims = tuple(
        f"{event.task_id}:{event.target_id}:{event.actor_id}"
        for event in world.events
        if event.action.value == "claim_task"
    )
    conversation_ids = tuple(
        sorted({record.conversation_id for record in message_trace.records})
    )
    feeding_status = next(
        (
            agent.workflow_status
            for agent in logistics_agents
            if agent.workflow_status is not None
        ),
        "not_completed",
    )
    medical_status = next(
        (
            agent.workflow_status
            for agent in veterinary_agents
            if agent.workflow_status is not None
        ),
        "not_completed",
    )
    success = (
        error is None
        and feeding_status == "completed"
        and medical_status == "completed"
        and feeding_task.status is TaskStatus.COMPLETED
        and medical_task.status is TaskStatus.COMPLETED
        and bowl.level == bowl.capacity
        and stock.quantity == food - 1
        and animal.health is HealthStatus.HEALTHY
        and medicine_stock.quantity == medicine - 1
        and max_occupancy <= 2
        and active_occupancy == 0
    )
    if error is None and not success:
        failure_reasons = [
            *(
                reason
                for agent in feeding_agents
                for reason in agent.failure_reasons.values()
            ),
            *(
                reason
                for agent in logistics_agents
                for reason in (*agent.failure_reasons.values(), *agent.transport_failures.values())
            ),
            *(
                reason
                for agent in veterinary_agents
                for reason in agent.failure_reasons.values()
            ),
        ]
        error = next(iter(failure_reasons), "one or more workflows did not complete")

    return SimulationResult(
        success=success,
        operator_count=config.operator_count,
        spade_agent_count=config.operator_count + 1,
        veterinary_agents=config.veterinary_agents,
        logistics_agents=config.logistics_agents,
        feeding_agents=config.feeding_agents,
        feeding_status=feeding_status,
        medical_status=medical_status,
        bowl_level=bowl.level,
        food_remaining=stock.quantity,
        animal_health=animal.health.value,
        medicine_remaining=medicine_stock.quantity,
        max_room_occupancy=max_occupancy,
        room_capacity=2,
        active_room_occupancy_at_end=active_occupancy,
        task_claims=claims,
        message_count=len(message_trace.records),
        conversation_ids=conversation_ids,
        logs=activity_log.lines,
        error=error,
    )


def run_simulation(
    config: SimulationConfig = SimulationConfig(),
    food: int = 2,
    medicine: int = 1,
    timeout_seconds: float = 30.0,
) -> SimulationResult:
    holder: dict[str, SimulationResult] = {}

    async def run() -> None:
        holder["result"] = await execute_simulation(
            config,
            food,
            medicine,
            timeout_seconds,
        )

    spade.run(run(), embedded_xmpp_server=True)
    return holder["result"]


def print_result(result: SimulationResult, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(asdict(result), sort_keys=True))
        return
    for line in result.logs:
        print(line)
    if result.success:
        print("SIMULATION OK")
        print(
            f"operators={result.operator_count} "
            f"veterinary={result.veterinary_agents} "
            f"logistics={result.logistics_agents} feeding={result.feeding_agents}"
        )
        print(
            f"feeding={result.feeding_status} medical={result.medical_status} "
            f"animal={result.animal_health} bowl={result.bowl_level}/1"
        )
        print(
            f"max-room-occupancy={result.max_room_occupancy}/"
            f"{result.room_capacity}"
        )
    else:
        print("SIMULATION FAILED")
        print(f"feeding={result.feeding_status} medical={result.medical_status}")
        print(f"reason={result.error}")
