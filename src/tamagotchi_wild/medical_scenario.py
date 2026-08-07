"""Fase 3: ciclo SPADE-BDI completo di trasporto, cura e rientro."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json

import spade

from tamagotchi_wild.agents import (
    EnvironmentAgent,
    LogisticsAgent,
    VeterinaryAgent,
)
from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    AgentRole,
    AgentState,
    Animal,
    HealthStatus,
    MedicineStock,
    Position,
    Task,
    TaskStatus,
    TaskType,
)
from tamagotchi_wild.environment import EnvironmentState
from tamagotchi_wild.observability import ActivityLog, MessageTrace


PASSWORD = "local-medical-password"
ENVIRONMENT_JID = "environment@localhost"
LOGISTICS_JID = "logistics_01@localhost"
VETERINARY_JID = "veterinary_01@localhost"
UNUSED_FEEDING_JID = "feeding_01@localhost"
TASK_ID = "medical_001"
ANIMAL_ID = "animal_001"
CAGE_ID = "cage_01"
MEDICINE_STOCK_ID = "medicine_stock_01"
CAGE_POSITION = Position(2, 4)
TREATMENT_POSITION = Position(9, 4)
MEDICAL_STORAGE_POSITION = Position(6, 1)


@dataclass(frozen=True, slots=True)
class MedicalScenarioResult:
    success: bool
    task_id: str
    scenario_status: str
    animal_health: str
    animal_position: tuple[int, int]
    animal_carried_by: str | None
    medicine_before: int
    medicine_after: int
    task_status: str
    logistics_bdi_ready: bool
    veterinary_bdi_ready: bool
    message_count: int
    conversation_ids: tuple[str, ...]
    logs: tuple[str, ...]
    error: str | None = None


def build_medical_environment(medicine_quantity: int = 1) -> EnvironmentState:
    world = create_default_environment()
    world.register_animal(
        Animal(ANIMAL_ID, "fox", CAGE_POSITION, HealthStatus.SICK)
    )
    world.register_medicine_stock(
        MedicineStock(
            MEDICINE_STOCK_ID,
            MEDICAL_STORAGE_POSITION,
            medicine_quantity,
        )
    )
    world.register_agent(
        AgentState(LOGISTICS_JID.split("@", 1)[0], AgentRole.LOGISTICS, CAGE_POSITION)
    )
    world.register_agent(
        AgentState(
            VETERINARY_JID.split("@", 1)[0],
            AgentRole.VETERINARY,
            TREATMENT_POSITION,
        )
    )
    world.register_task(Task(TASK_ID, TaskType.TREAT_ANIMAL, ANIMAL_ID))
    return world


async def execute_medical_scenario(
    medicine_quantity: int = 1,
    timeout_seconds: float = 20.0,
) -> MedicalScenarioResult:
    world = build_medical_environment(medicine_quantity)
    activity_log = ActivityLog()
    message_trace = MessageTrace()
    environment = EnvironmentAgent(
        ENVIRONMENT_JID,
        PASSWORD,
        world,
        activity_log,
        message_trace,
    )
    logistics = LogisticsAgent(
        LOGISTICS_JID,
        PASSWORD,
        UNUSED_FEEDING_JID,
        activity_log,
        message_trace,
        timeout_seconds,
        environment_jid=ENVIRONMENT_JID,
        cage_position=CAGE_POSITION,
        treatment_position=TREATMENT_POSITION,
    )
    veterinary = VeterinaryAgent(
        VETERINARY_JID,
        PASSWORD,
        LOGISTICS_JID,
        ENVIRONMENT_JID,
        MEDICINE_STOCK_ID,
        TREATMENT_POSITION,
        activity_log,
        message_trace,
        timeout_seconds,
    )
    error: str | None = None

    try:
        await environment.start(auto_register=True)
        await logistics.start(auto_register=True)
        await veterinary.start(auto_register=True)
        await asyncio.wait_for(
            asyncio.gather(
                logistics.bdi_ready.wait(),
                veterinary.bdi_ready.wait(),
            ),
            timeout=timeout_seconds,
        )
        await environment.publish_sick_animal(
            VETERINARY_JID,
            TASK_ID,
            ANIMAL_ID,
            CAGE_ID,
        )
        await asyncio.wait_for(veterinary.scenario_done.wait(), timeout=timeout_seconds)
    except TimeoutError:
        error = f"medical scenario timed out after {timeout_seconds:g} seconds"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        await veterinary.stop()
        await logistics.stop()
        await environment.stop()

    snapshot = world.snapshot()
    animal = next(item for item in snapshot.animals if item.id == ANIMAL_ID)
    medicine = next(
        item for item in snapshot.medicine_stocks if item.id == MEDICINE_STOCK_ID
    )
    task = next(item for item in snapshot.tasks if item.id == TASK_ID)
    conversation_ids = tuple(
        sorted({record.conversation_id for record in message_trace.records})
    )
    expected_success = (
        error is None
        and veterinary.scenario_status == "completed"
        and animal.health is HealthStatus.HEALTHY
        and animal.position == CAGE_POSITION
        and animal.carried_by is None
        and medicine.quantity == medicine_quantity - 1
        and task.status is TaskStatus.COMPLETED
        and conversation_ids == (TASK_ID,)
    )
    failure_reason = error
    if failure_reason is None and not expected_success:
        failure_reason = veterinary.failure_reasons.get(TASK_ID)

    return MedicalScenarioResult(
        success=expected_success,
        task_id=TASK_ID,
        scenario_status=veterinary.scenario_status or "not_completed",
        animal_health=animal.health.value,
        animal_position=(animal.position.x, animal.position.y),
        animal_carried_by=animal.carried_by,
        medicine_before=medicine_quantity,
        medicine_after=medicine.quantity,
        task_status=task.status.value,
        logistics_bdi_ready=logistics.bdi_ready.is_set(),
        veterinary_bdi_ready=veterinary.bdi_ready.is_set(),
        message_count=len(message_trace.records),
        conversation_ids=conversation_ids,
        logs=activity_log.lines,
        error=failure_reason,
    )


def run_medical_scenario(
    medicine_quantity: int = 1,
    timeout_seconds: float = 20.0,
) -> MedicalScenarioResult:
    result_holder: dict[str, MedicalScenarioResult] = {}

    async def scenario() -> None:
        result_holder["result"] = await execute_medical_scenario(
            medicine_quantity,
            timeout_seconds,
        )

    spade.run(scenario(), embedded_xmpp_server=True)
    return result_holder["result"]


def print_result(result: MedicalScenarioResult, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(asdict(result), sort_keys=True))
        return
    for line in result.logs:
        print(line)
    if result.success:
        print("PHASE 3 OK")
        print(f"task={result.task_id} status={result.task_status}")
        print(
            f"animal={result.animal_health} "
            f"position={result.animal_position[0]},{result.animal_position[1]}"
        )
        print(f"medicine={result.medicine_before}->{result.medicine_after}")
        print(
            f"messages={result.message_count} "
            f"conversation-id={result.conversation_ids[0]}"
        )
    else:
        print("PHASE 3 FAILED")
        print(f"task={result.task_id} status={result.scenario_status}")
        print(f"reason={result.error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--medicine", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.medicine < 0:
        raise SystemExit("--medicine must not be negative")
    result = run_medical_scenario(args.medicine, args.timeout)
    print_result(result, args.as_json)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
