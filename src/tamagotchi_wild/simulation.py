
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json
from queue import Queue

import spade

from tamagotchi_wild.agents import (
    EnvironmentAgent,
    FeedingAgent,
    LogisticsAgent,
    VisualizationAgent,
    VeterinaryAgent,
)
from tamagotchi_wild.config import SimulationConfig, create_default_environment
from tamagotchi_wild.domain import (
    AgentRole,
    AgentState,
    Animal,
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
from tamagotchi_wild.environment import EnvironmentState
from tamagotchi_wild.observability import ActivityLog, MessageTrace


PASSWORD = "local-cras-password"
ENVIRONMENT_JID = "environment@localhost"
VISUALIZATION_JID = "visualization@localhost"
FOOD_STOCK_ID = "food_stock_01"
MEDICINE_STOCK_ID = "medicine_stock_01"
FOOD_POSITION = Position(1, 1)
MEDICINE_POSITION = Position(6, 1)
CAGE_POSITION = Position(2, 4)
TREATMENT_POSITION = Position(9, 4)

SPECIES = (
    "fox",
    "owl",
    "hedgehog",
    "badger",
    "hare",
    "deer",
    "squirrel",
    "tortoise",
    "heron",
    "bat",
)
MEDICAL_CONDITIONS = (
    "wing_injury",
    "dehydration",
    "respiratory_infection",
    "leg_fracture",
    "malnutrition",
    "skin_wound",
    "parasites",
    "eye_infection",
    "burn_injury",
    "hypothermia",
)


@dataclass(frozen=True, slots=True)
class AnimalCase:
    animal_id: str
    cage_id: str
    bowl_id: str
    feeding_task_id: str
    medical_task_id: str
    position: Position
    species: str
    condition: str


@dataclass(frozen=True, slots=True)
class SimulationResult:
    success: bool
    operator_count: int
    spade_agent_count: int
    veterinary_agents: int
    logistics_agents: int
    feeding_agents: int
    animal_count: int
    cage_count: int
    bowl_count: int
    feeding_task_count: int
    medical_task_count: int
    completed_feeding_tasks: int
    completed_medical_tasks: int
    healthy_animals: int
    filled_bowls: int
    feeding_status: str
    medical_status: str
    food_remaining: int
    medicine_remaining: int
    animal_conditions: tuple[str, ...]
    max_room_occupancy: int
    room_capacity: int
    max_treatment_patients: int
    treatment_patient_capacity: int
    max_carried_animals_per_agent: int
    active_room_occupancy_at_end: int
    task_claims: tuple[str, ...]
    message_count: int
    conversation_ids: tuple[str, ...]
    logs: tuple[str, ...]
    error: str | None = None


def case_definitions(config: SimulationConfig) -> tuple[AnimalCase, ...]:

    template_world = create_default_environment()
    cage_area = next(
        area
        for area in template_world.snapshot().areas
        if area.kind is AreaType.CAGE_AREA
    )
    ordered_cells = (CAGE_POSITION,) + tuple(
        position
        for position in sorted(cage_area.cells, key=lambda item: (item.y, item.x))
        if position != CAGE_POSITION
    )
    cases = []
    for index, position in enumerate(
        ordered_cells[: config.animal_count],
        start=1,
    ):
        condition = (
            MEDICAL_CONDITIONS[index - 1]
            if index <= len(MEDICAL_CONDITIONS)
            else f"other_condition_{index:03d}"
        )
        cases.append(
            AnimalCase(
                animal_id=f"animal_{index:03d}",
                cage_id=f"cage_{index:02d}",
                bowl_id=f"bowl_{index:02d}",
                feeding_task_id=f"feeding_{index:03d}",
                medical_task_id=f"medical_{index:03d}",
                position=position,
                species=SPECIES[(index - 1) % len(SPECIES)],
                condition=condition,
            )
        )
    return tuple(cases)


def build_environment(
    config: SimulationConfig,
    food: int,
    medicine: int,
) -> EnvironmentState:
    world = create_default_environment()
    cases = case_definitions(config)
    world.register_food_stock(FoodStock(FOOD_STOCK_ID, FOOD_POSITION, food))
    world.register_medicine_stock(
        MedicineStock(MEDICINE_STOCK_ID, MEDICINE_POSITION, medicine)
    )
    for case in cases:
        world.register_cage(
            Cage(case.cage_id, case.position, case.animal_id, case.bowl_id)
        )
        world.register_bowl(Bowl(case.bowl_id, case.cage_id, case.position))
        world.register_animal(
            Animal(
                case.animal_id,
                case.species,
                case.position,
                health=HealthStatus.SICK,
                condition=case.condition,
                cage_id=case.cage_id,
            )
        )
        world.register_task(
            Task(case.feeding_task_id, TaskType.REFILL_BOWL, case.bowl_id)
        )
        world.register_task(
            Task(case.medical_task_id, TaskType.TREAT_ANIMAL, case.animal_id)
        )

    identities = (
        *(
            (jid, AgentRole.VETERINARY)
            for jid in config.jids("veterinary", config.veterinary_agents)
        ),
        *(
            (jid, AgentRole.LOGISTICS)
            for jid in config.jids("logistics", config.logistics_agents)
        ),
        *(
            (jid, AgentRole.FEEDING)
            for jid in config.jids("feeding", config.feeding_agents)
        ),
    )
    staging_positions = (
        Position(1, 1),
        Position(5, 1),
        Position(2, 4),
        Position(9, 4),
        Position(2, 1),
        Position(6, 1),
        Position(3, 4),
        Position(7, 1),
        Position(4, 4),
        Position(10, 4),
        Position(1, 2),
        Position(8, 1),
        Position(5, 4),
        Position(9, 5),
        Position(2, 2),
        Position(10, 5),
    )
    for index, (jid, role) in enumerate(identities):
        position = staging_positions[index % len(staging_positions)]
        world.register_agent(AgentState(jid.split("@", 1)[0], role, position))
    return world


def _workflow_outcomes(agents) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for agent in agents:
        outcomes.update(agent.workflow_outcomes)
    return outcomes


async def _wait_for_workflows(
    agents,
    task_ids: frozenset[str],
    timeout_seconds: float,
) -> None:
    async def wait() -> None:
        while not task_ids.issubset(_workflow_outcomes(agents)):
            await asyncio.sleep(0.05)

    await asyncio.wait_for(wait(), timeout=timeout_seconds)


async def execute_simulation(
    config: SimulationConfig = SimulationConfig(),
    food: int | None = None,
    medicine: int | None = None,
    timeout_seconds: float = 60.0,
    visualization_queue: Queue | None = None,
) -> SimulationResult:
    food_quantity = config.animal_count if food is None else food
    medicine_quantity = config.animal_count if medicine is None else medicine
    world = build_environment(config, food_quantity, medicine_quantity)
    cases = case_definitions(config)
    activity_log = ActivityLog()
    message_trace = MessageTrace()
    feeding_jids = config.jids("feeding", config.feeding_agents)
    logistics_jids = config.jids("logistics", config.logistics_agents)
    veterinary_jids = config.jids("veterinary", config.veterinary_agents)
    bowl_positions = {case.bowl_id: case.position for case in cases}
    cage_positions = {case.cage_id: case.position for case in cases}

    environment = EnvironmentAgent(
        ENVIRONMENT_JID,
        PASSWORD,
        world,
        activity_log,
        message_trace,
        visualization_jid=(
            VISUALIZATION_JID if visualization_queue is not None else None
        ),
    )
    visualization = (
        VisualizationAgent(VISUALIZATION_JID, PASSWORD, visualization_queue)
        if visualization_queue is not None
        else None
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
            bowl_positions=bowl_positions,
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
            cage_positions=cage_positions,
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
        if visualization is not None:
            await visualization.start(auto_register=True)
            started.append(visualization)
            await asyncio.wait_for(
                visualization.ready.wait(),
                timeout=timeout_seconds,
            )
        await environment.start(auto_register=True)
        started.append(environment)
        for agent in operators:
            await agent.start(auto_register=True)
            started.append(agent)
        await asyncio.wait_for(
            asyncio.gather(*(agent.bdi_ready.wait() for agent in operators)),
            timeout=timeout_seconds,
        )
        if visualization is not None:
            await environment.publish_initial_visual_state(timeout_seconds)

        await asyncio.gather(
            *(
                environment.publish_bowl_empty(
                    logistics_jids[(index - 1) % len(logistics_jids)],
                    case.feeding_task_id,
                    case.cage_id,
                    case.bowl_id,
                )
                for index, case in enumerate(cases, start=1)
            ),
            *(
                environment.publish_sick_animal(
                    veterinary_jids[(index - 1) % len(veterinary_jids)],
                    case.medical_task_id,
                    case.animal_id,
                    case.cage_id,
                )
                for index, case in enumerate(cases, start=1)
            ),
        )
        await asyncio.gather(
            _wait_for_workflows(
                logistics_agents,
                frozenset(case.feeding_task_id for case in cases),
                timeout_seconds,
            ),
            _wait_for_workflows(
                veterinary_agents,
                frozenset(case.medical_task_id for case in cases),
                timeout_seconds,
            ),
        )
        if visualization is not None:
            await asyncio.sleep(0.2)
    except TimeoutError:
        error = f"integrated simulation timed out after {timeout_seconds:g} seconds"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        for agent in reversed(started):
            await agent.stop()

    snapshot = world.snapshot()
    stock = next(item for item in snapshot.food_stocks if item.id == FOOD_STOCK_ID)
    medicine_stock = next(
        item for item in snapshot.medicine_stocks if item.id == MEDICINE_STOCK_ID
    )
    feeding_tasks = tuple(
        task for task in snapshot.tasks if task.kind is TaskType.REFILL_BOWL
    )
    medical_tasks = tuple(
        task for task in snapshot.tasks if task.kind is TaskType.TREAT_ANIMAL
    )
    completed_feeding = sum(
        task.status is TaskStatus.COMPLETED for task in feeding_tasks
    )
    completed_medical = sum(
        task.status is TaskStatus.COMPLETED for task in medical_tasks
    )
    healthy_animals = sum(
        animal.health is HealthStatus.HEALTHY for animal in snapshot.animals
    )
    filled_bowls = sum(bowl.level == bowl.capacity for bowl in snapshot.bowls)
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
    feeding_outcomes = _workflow_outcomes(logistics_agents)
    medical_outcomes = _workflow_outcomes(veterinary_agents)
    feeding_status = (
        "completed"
        if all(
            feeding_outcomes.get(case.feeding_task_id) == "completed"
            for case in cases
        )
        else "failed"
    )
    medical_status = (
        "completed"
        if all(
            medical_outcomes.get(case.medical_task_id) == "completed"
            for case in cases
        )
        else "failed"
    )
    success = (
        error is None
        and feeding_status == "completed"
        and medical_status == "completed"
        and completed_feeding == config.animal_count
        and completed_medical == config.animal_count
        and filled_bowls == config.animal_count
        and healthy_animals == config.animal_count
        and stock.quantity == food_quantity - config.animal_count
        and medicine_stock.quantity == medicine_quantity - config.animal_count
        and max_occupancy <= 2
        and snapshot.max_treatment_patients
        <= snapshot.treatment_patient_capacity
        and snapshot.max_carried_animals_per_agent <= 1
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
                for reason in (
                    *agent.failure_reasons.values(),
                    *agent.transport_failures.values(),
                )
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
        spade_agent_count=(
            config.operator_count + 1 + (1 if visualization is not None else 0)
        ),
        veterinary_agents=config.veterinary_agents,
        logistics_agents=config.logistics_agents,
        feeding_agents=config.feeding_agents,
        animal_count=len(snapshot.animals),
        cage_count=len(snapshot.cages),
        bowl_count=len(snapshot.bowls),
        feeding_task_count=len(feeding_tasks),
        medical_task_count=len(medical_tasks),
        completed_feeding_tasks=completed_feeding,
        completed_medical_tasks=completed_medical,
        healthy_animals=healthy_animals,
        filled_bowls=filled_bowls,
        feeding_status=feeding_status,
        medical_status=medical_status,
        food_remaining=stock.quantity,
        medicine_remaining=medicine_stock.quantity,
        animal_conditions=tuple(
            f"{animal.id}:{animal.species}:{animal.condition}"
            for animal in snapshot.animals
        ),
        max_room_occupancy=max_occupancy,
        room_capacity=2,
        max_treatment_patients=snapshot.max_treatment_patients,
        treatment_patient_capacity=snapshot.treatment_patient_capacity,
        max_carried_animals_per_agent=(
            snapshot.max_carried_animals_per_agent
        ),
        active_room_occupancy_at_end=active_occupancy,
        task_claims=claims,
        message_count=len(message_trace.records),
        conversation_ids=conversation_ids,
        logs=activity_log.lines,
        error=error,
    )


def run_simulation(
    config: SimulationConfig = SimulationConfig(),
    food: int | None = None,
    medicine: int | None = None,
    timeout_seconds: float = 60.0,
    visualization_queue: Queue | None = None,
) -> SimulationResult:
    holder: dict[str, Any] = {}

    async def run() -> None:
        try:
            holder["result"] = await execute_simulation(
                config,
                food,
                medicine,
                timeout_seconds,
                visualization_queue,
            )
        except Exception as exc:
            holder["error"] = exc

    spade.run(run(), embedded_xmpp_server=True)
    if "error" in holder:
        raise holder["error"]
    if "result" not in holder:
        raise RuntimeError("simulation runner exited without producing a result")
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
            f"animals={result.animal_count} cages={result.cage_count} "
            f"bowls={result.bowl_count}"
        )
        print(
            f"feeding={result.completed_feeding_tasks}/{result.feeding_task_count} "
            f"medical={result.completed_medical_tasks}/{result.medical_task_count} "
            f"healthy={result.healthy_animals}/{result.animal_count}"
        )
        print(
            f"max-room-occupancy={result.max_room_occupancy}/"
            f"{result.room_capacity}"
        )
        print(
            f"max-treatment-patients={result.max_treatment_patients}/"
            f"{result.treatment_patient_capacity} "
            f"max-carried-per-logistics="
            f"{result.max_carried_animals_per_agent}/1"
        )
    else:
        print("SIMULATION FAILED")
        print(f"feeding={result.feeding_status} medical={result.medical_status}")
        print(f"reason={result.error}")
