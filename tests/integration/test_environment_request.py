import json

from tamagotchi_wild.agents import process_action_request
from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    ActionType,
    AgentRole,
    AgentState,
    Bowl,
    FoodStock,
    Position,
    Task,
    TaskType,
)
from tamagotchi_wild.messaging import ActionRequest


def test_json_request_reaches_authoritative_environment() -> None:
    world = create_default_environment()
    world.register_agent(
        AgentState("logistics-001", AgentRole.LOGISTICS, Position(2, 4))
    )
    request = ActionRequest(
        task_id="task-001",
        actor_id="logistics-001",
        target_id="logistics-001",
        requested_action=ActionType.MOVE_AGENT,
        destination=Position(8, 4),
    )

    response = process_action_request(world, request.to_json())

    assert response.accepted is True
    assert response.task_id == "task-001"
    assert world.snapshot().agents[0].position == Position(8, 4)


def test_invalid_json_is_rejected_without_an_event() -> None:
    world = create_default_environment()

    response = process_action_request(world, json.dumps({"schema_version": 1}))

    assert response.accepted is False
    assert response.task_id == "unknown"
    assert world.events == ()


def test_feeding_actions_are_applied_through_json_contracts() -> None:
    world = create_default_environment()
    world.register_bowl(Bowl("bowl_01", "cage_01", Position(2, 4)))
    world.register_food_stock(FoodStock("food_stock_01", Position(1, 1), 2))
    world.register_task(Task("task_001", TaskType.REFILL_BOWL, "bowl_01"))

    take_response = process_action_request(
        world,
        ActionRequest(
            task_id="task_001",
            actor_id="feeding_01",
            target_id="food_stock_01",
            requested_action=ActionType.TAKE_FOOD,
            quantity=1,
        ).to_json(),
    )
    fill_response = process_action_request(
        world,
        ActionRequest(
            task_id="task_001",
            actor_id="feeding_01",
            target_id="bowl_01",
            requested_action=ActionType.FILL_BOWL,
            quantity=1,
        ).to_json(),
    )

    assert take_response.accepted is True
    assert fill_response.accepted is True
    assert world.snapshot().food_stocks[0].quantity == 1
    assert world.snapshot().bowls[0].level == 1
