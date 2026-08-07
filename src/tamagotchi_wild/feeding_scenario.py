"""Fase 2: scenario SPADE-BDI completo per il rifornimento di una ciotola."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import json

import spade

from tamagotchi_wild.agents import EnvironmentAgent, FeedingAgent, LogisticsAgent
from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    AgentRole,
    AgentState,
    Bowl,
    FoodStock,
    Position,
    Task,
    TaskStatus,
    TaskType,
)
from tamagotchi_wild.environment import EnvironmentState
from tamagotchi_wild.observability import ActivityLog, MessageTrace


PASSWORD = "local-feeding-password"
ENVIRONMENT_JID = "environment@localhost"
FEEDING_JID = "feeding_01@localhost"
LOGISTICS_JID = "logistics_01@localhost"
TASK_ID = "task_001"
CAGE_ID = "cage_01"
BOWL_ID = "bowl_01"
FOOD_STOCK_ID = "food_stock_01"


@dataclass(frozen=True, slots=True)
class FeedingScenarioResult:
    success: bool
    task_id: str
    scenario_status: str
    bowl_level: int
    bowl_capacity: int
    food_before: int
    food_after: int
    task_status: str
    logistics_bdi_ready: bool
    feeding_bdi_ready: bool
    feeding_bdi_outcome: str | None
    message_count: int
    conversation_ids: tuple[str, ...]
    logs: tuple[str, ...]
    error: str | None = None


def build_feeding_environment(food_quantity: int = 2) -> EnvironmentState:
    world = create_default_environment()
    world.register_bowl(Bowl(BOWL_ID, CAGE_ID, Position(2, 4)))
    world.register_food_stock(
        FoodStock(FOOD_STOCK_ID, Position(1, 1), food_quantity)
    )
    world.register_agent(
        AgentState(FEEDING_JID.split("@", 1)[0], AgentRole.FEEDING, Position(1, 1))
    )
    world.register_agent(
        AgentState(
            LOGISTICS_JID.split("@", 1)[0],
            AgentRole.LOGISTICS,
            Position(3, 4),
        )
    )
    world.register_task(Task(TASK_ID, TaskType.REFILL_BOWL, BOWL_ID))
    return world


async def execute_feeding_scenario(
    food_quantity: int = 2,
    timeout_seconds: float = 15.0,
) -> FeedingScenarioResult:
    world = build_feeding_environment(food_quantity)
    activity_log = ActivityLog()
    message_trace = MessageTrace()
    environment = EnvironmentAgent(
        ENVIRONMENT_JID,
        PASSWORD,
        world,
        activity_log,
        message_trace,
    )
    feeding = FeedingAgent(
        FEEDING_JID,
        PASSWORD,
        ENVIRONMENT_JID,
        FOOD_STOCK_ID,
        activity_log,
        message_trace,
        timeout_seconds,
    )
    logistics = LogisticsAgent(
        LOGISTICS_JID,
        PASSWORD,
        FEEDING_JID,
        activity_log,
        message_trace,
        timeout_seconds,
    )
    error: str | None = None

    try:
        await environment.start(auto_register=True)
        await feeding.start(auto_register=True)
        await logistics.start(auto_register=True)
        await asyncio.wait_for(
            asyncio.gather(
                feeding.bdi_ready.wait(),
                logistics.bdi_ready.wait(),
            ),
            timeout=timeout_seconds,
        )
        await environment.publish_bowl_empty(
            LOGISTICS_JID,
            TASK_ID,
            CAGE_ID,
            BOWL_ID,
        )
        await asyncio.wait_for(logistics.scenario_done.wait(), timeout=timeout_seconds)
        await asyncio.wait_for(feeding.bdi_outcome_ready.wait(), timeout=timeout_seconds)
    except TimeoutError:
        error = f"feeding scenario timed out after {timeout_seconds:g} seconds"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        await logistics.stop()
        await feeding.stop()
        await environment.stop()

    snapshot = world.snapshot()
    bowl = next(item for item in snapshot.bowls if item.id == BOWL_ID)
    stock = next(item for item in snapshot.food_stocks if item.id == FOOD_STOCK_ID)
    task = next(item for item in snapshot.tasks if item.id == TASK_ID)
    conversation_ids = tuple(
        sorted({record.conversation_id for record in message_trace.records})
    )
    expected_success = (
        error is None
        and logistics.scenario_status == "completed"
        and feeding.bdi_outcomes.get(TASK_ID) == "completed"
        and bowl.level == bowl.capacity
        and stock.quantity == food_quantity - 1
        and task.status is TaskStatus.COMPLETED
        and conversation_ids == (TASK_ID,)
    )
    failure_reason = error
    if failure_reason is None and not expected_success:
        failure_reason = logistics.failure_reasons.get(TASK_ID)

    return FeedingScenarioResult(
        success=expected_success,
        task_id=TASK_ID,
        scenario_status=logistics.scenario_status or "not_completed",
        bowl_level=bowl.level,
        bowl_capacity=bowl.capacity,
        food_before=food_quantity,
        food_after=stock.quantity,
        task_status=task.status.value,
        logistics_bdi_ready=logistics.bdi_ready.is_set(),
        feeding_bdi_ready=feeding.bdi_ready.is_set(),
        feeding_bdi_outcome=feeding.bdi_outcomes.get(TASK_ID),
        message_count=len(message_trace.records),
        conversation_ids=conversation_ids,
        logs=activity_log.lines,
        error=failure_reason,
    )


def run_feeding_scenario(
    food_quantity: int = 2,
    timeout_seconds: float = 15.0,
) -> FeedingScenarioResult:
    result_holder: dict[str, FeedingScenarioResult] = {}

    async def scenario() -> None:
        result_holder["result"] = await execute_feeding_scenario(
            food_quantity,
            timeout_seconds,
        )

    spade.run(scenario(), embedded_xmpp_server=True)
    return result_holder["result"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--food", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def print_result(result: FeedingScenarioResult, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(asdict(result), sort_keys=True))
        return
    for line in result.logs:
        print(line)
    if result.success:
        print("PHASE 2 OK")
        print(f"task={result.task_id} status={result.task_status}")
        print(
            f"food={result.food_before}->{result.food_after} "
            f"bowl={result.bowl_level}/{result.bowl_capacity}"
        )
        print(
            f"messages={result.message_count} "
            f"conversation-id={result.conversation_ids[0]}"
        )
    else:
        print("PHASE 2 FAILED")
        print(f"task={result.task_id} status={result.scenario_status}")
        print(f"reason={result.error}")


def main() -> int:
    args = build_parser().parse_args()
    if args.food < 0:
        raise SystemExit("--food must not be negative")
    result = run_feeding_scenario(args.food, args.timeout)
    print_result(result, args.as_json)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
