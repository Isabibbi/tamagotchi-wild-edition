import json

from tamagotchi_wild.agents import process_action_request
from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import AgentRole, AgentState, Position
from tamagotchi_wild.messaging import ActionRequest
from tamagotchi_wild.domain import ActionType


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
