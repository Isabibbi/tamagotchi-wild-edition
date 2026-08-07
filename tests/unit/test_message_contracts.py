import json

import pytest

from tamagotchi_wild.domain import ActionType, Position
from tamagotchi_wild.messaging import (
    ActionRequest,
    MessageContractError,
    request_metadata,
)


def test_action_request_round_trip_preserves_typed_data() -> None:
    original = ActionRequest(
        task_id="task-001",
        actor_id="logistics-001",
        target_id="logistics-001",
        requested_action=ActionType.MOVE_AGENT,
        destination=Position(8, 4),
    )

    restored = ActionRequest.from_json(original.to_json())

    assert restored == original
    assert restored.to_command().destination == Position(8, 4)


def test_unknown_schema_version_is_rejected() -> None:
    payload = {
        "schema_version": 99,
        "task_id": "task-001",
        "actor_id": "logistics-001",
        "target_id": "logistics-001",
        "requested_action": "move_agent",
    }

    with pytest.raises(MessageContractError, match="schema_version"):
        ActionRequest.from_json(json.dumps(payload))


def test_metadata_contains_fipa_routing_and_correlation() -> None:
    metadata = request_metadata("task-001")

    assert metadata == {
        "performative": "request",
        "ontology": "cras.environment",
        "language": "json",
        "conversation-id": "task-001",
    }
