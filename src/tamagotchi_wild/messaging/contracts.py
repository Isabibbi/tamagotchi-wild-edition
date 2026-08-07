"""Contratti JSON versionati per le richieste indirizzate all'ambiente."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from tamagotchi_wild.domain import (
    ActionCommand,
    ActionResult,
    ActionType,
    HealthStatus,
    Position,
)


ENVIRONMENT_ONTOLOGY = "cras.environment"
MESSAGE_LANGUAGE = "json"
SCHEMA_VERSION = 1


class MessageContractError(ValueError):
    """Raised when a message body does not respect the public contract."""


@dataclass(frozen=True, slots=True)
class ActionRequest:
    task_id: str
    actor_id: str
    target_id: str
    requested_action: ActionType
    destination: Position | None = None
    health: HealthStatus | None = None
    schema_version: int = SCHEMA_VERSION

    def to_command(self) -> ActionCommand:
        return ActionCommand(
            actor_id=self.actor_id,
            action=self.requested_action,
            target_id=self.target_id,
            destination=self.destination,
            health=self.health,
        )

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "requested_action": self.requested_action.value,
        }
        if self.destination is not None:
            payload["destination"] = {
                "x": self.destination.x,
                "y": self.destination.y,
            }
        if self.health is not None:
            payload["health"] = self.health.value
        return json.dumps(payload, sort_keys=True)

    @classmethod
    def from_json(cls, body: str) -> ActionRequest:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, TypeError) as exc:
            raise MessageContractError("message body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise MessageContractError("message body must be a JSON object")

        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise MessageContractError(f"unsupported schema_version: {version}")

        task_id = _required_text(payload, "task_id")
        actor_id = _required_text(payload, "actor_id")
        target_id = _required_text(payload, "target_id")
        action = _enum_value(ActionType, payload.get("requested_action"), "requested_action")
        destination = _optional_position(payload.get("destination"))
        health = _optional_enum(HealthStatus, payload.get("health"), "health")
        return cls(
            task_id=task_id,
            actor_id=actor_id,
            target_id=target_id,
            requested_action=action,
            destination=destination,
            health=health,
        )


@dataclass(frozen=True, slots=True)
class ActionResponse:
    task_id: str
    accepted: bool
    reason: str
    event_sequence: int | None
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_result(cls, task_id: str, result: ActionResult) -> ActionResponse:
        return cls(
            task_id=task_id,
            accepted=result.accepted,
            reason=result.reason,
            event_sequence=result.event_sequence,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "task_id": self.task_id,
                "accepted": self.accepted,
                "reason": self.reason,
                "event_sequence": self.event_sequence,
            },
            sort_keys=True,
        )


def request_metadata(task_id: str) -> dict[str, str]:
    return {
        "performative": "request",
        "ontology": ENVIRONMENT_ONTOLOGY,
        "language": MESSAGE_LANGUAGE,
        "conversation-id": task_id,
    }


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MessageContractError(f"{field} must be a non-empty string")
    return value


def _enum_value(enum_type, value, field):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise MessageContractError(f"invalid {field}: {value}") from exc


def _optional_enum(enum_type, value, field):
    if value is None:
        return None
    return _enum_value(enum_type, value, field)


def _optional_position(value: Any) -> Position | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise MessageContractError("destination must be an object with x and y")
    x = value.get("x")
    y = value.get("y")
    if type(x) is not int or type(y) is not int:
        raise MessageContractError("destination x and y must be integers")
    return Position(x, y)
