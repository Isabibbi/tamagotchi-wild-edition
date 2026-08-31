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
from tamagotchi_wild.environment import EnvironmentEvent, WorldSnapshot


# ============================================================================
# FIPA Metadata, Ontologies and Constants
# ============================================================================

SCHEMA_VERSION = 1
MESSAGE_LANGUAGE = "json"

ENVIRONMENT_ONTOLOGY = "cras.environment"
FEEDING_ONTOLOGY = "cras.feeding"
PERCEPTION_ONTOLOGY = "cras.perception"
TRANSPORT_ONTOLOGY = "cras.transport"
VISUALIZATION_ONTOLOGY = "cras.visualization"

OUTBOUND = "outbound"
RETURN = "return"


class MessageContractError(ValueError):
    pass


def request_metadata(task_id: str) -> dict[str, str]:
    return {
        "performative": "request",
        "ontology": ENVIRONMENT_ONTOLOGY,
        "language": MESSAGE_LANGUAGE,
        "conversation-id": task_id,
    }


def workflow_metadata(
    ontology: str,
    performative: str,
    task_id: str,
) -> dict[str, str]:
    return {
        "performative": performative,
        "ontology": ontology,
        "language": MESSAGE_LANGUAGE,
        "conversation-id": task_id,
    }


# ============================================================================
# Environment Action Contracts (Request / Response)
# ============================================================================

@dataclass(frozen=True, slots=True)
class ActionRequest:
    task_id: str
    actor_id: str
    target_id: str
    requested_action: ActionType
    destination: Position | None = None
    health: HealthStatus | None = None
    quantity: int | None = None
    schema_version: int = SCHEMA_VERSION

    def to_command(self) -> ActionCommand:
        return ActionCommand(
            actor_id=self.actor_id,
            action=self.requested_action,
            target_id=self.target_id,
            destination=self.destination,
            health=self.health,
            task_id=self.task_id,
            quantity=self.quantity,
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
        if self.quantity is not None:
            payload["quantity"] = self.quantity
        return json.dumps(payload, sort_keys=True)

    @classmethod
    def from_json(cls, body: str) -> ActionRequest:
        payload = _decode(body)
        task_id = _text(payload, "task_id")
        actor_id = _text(payload, "actor_id")
        target_id = _text(payload, "target_id")
        action = _enum_value(ActionType, payload.get("requested_action"), "requested_action")
        destination = _optional_position(payload.get("destination"))
        health = _optional_enum(HealthStatus, payload.get("health"), "health")
        quantity = _optional_positive_integer(payload.get("quantity"), "quantity")
        return cls(
            task_id=task_id,
            actor_id=actor_id,
            target_id=target_id,
            requested_action=action,
            destination=destination,
            health=health,
            quantity=quantity,
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

    @classmethod
    def from_json(cls, body: str) -> ActionResponse:
        payload = _decode(body)
        task_id = _text(payload, "task_id")
        accepted = payload.get("accepted")
        if type(accepted) is not bool:
            raise MessageContractError("accepted must be a boolean")
        reason = _text(payload, "reason")
        event_sequence = payload.get("event_sequence")
        if event_sequence is not None and type(event_sequence) is not int:
            raise MessageContractError("event_sequence must be an integer or null")
        return cls(task_id, accepted, reason, event_sequence)


# ============================================================================
# Feeding & Bowl Perception Contracts
# ============================================================================

@dataclass(frozen=True, slots=True)
class BowlEmptyPerception:
    task_id: str
    cage_id: str
    bowl_id: str

    def to_json(self) -> str:
        return _encode(self.task_id, self.cage_id, self.bowl_id, "bowl_empty")

    @classmethod
    def from_json(cls, body: str) -> BowlEmptyPerception:
        payload = _decode(body)
        if payload.get("event") != "bowl_empty":
            raise MessageContractError("expected bowl_empty perception")
        return cls(
            _text(payload, "task_id"),
            _text(payload, "cage_id"),
            _text(payload, "bowl_id"),
        )


@dataclass(frozen=True, slots=True)
class FeedingTaskRequest:
    task_id: str
    cage_id: str
    bowl_id: str

    def to_json(self) -> str:
        return _encode(self.task_id, self.cage_id, self.bowl_id, "refill_bowl")

    @classmethod
    def from_json(cls, body: str) -> FeedingTaskRequest:
        payload = _decode(body)
        if payload.get("event") != "refill_bowl":
            raise MessageContractError("expected refill_bowl request")
        return cls(
            _text(payload, "task_id"),
            _text(payload, "cage_id"),
            _text(payload, "bowl_id"),
        )


@dataclass(frozen=True, slots=True)
class FeedingStatus:
    task_id: str
    status: str
    reason: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "task_id": self.task_id,
                "status": self.status,
                "reason": self.reason,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, body: str) -> FeedingStatus:
        payload = _decode(body)
        status = _text(payload, "status")
        if status not in {"accepted", "completed", "failed", "refused"}:
            raise MessageContractError(f"invalid feeding status: {status}")
        reason = payload.get("reason", "")
        if not isinstance(reason, str):
            raise MessageContractError("reason must be a string")
        return cls(_text(payload, "task_id"), status, reason)


# ============================================================================
# Medical & Transport Contracts
# ============================================================================

@dataclass(frozen=True, slots=True)
class SickAnimalPerception:
    task_id: str
    animal_id: str
    cage_id: str

    def to_json(self) -> str:
        return _encode_medical(
            self.task_id,
            self.animal_id,
            self.cage_id,
            event="animal_sick",
        )

    @classmethod
    def from_json(cls, body: str) -> SickAnimalPerception:
        payload = _decode(body)
        if payload.get("event") != "animal_sick":
            raise MessageContractError("expected animal_sick perception")
        return cls(
            _text(payload, "task_id"),
            _text(payload, "animal_id"),
            _text(payload, "cage_id"),
        )


@dataclass(frozen=True, slots=True)
class TransportRequest:
    task_id: str
    animal_id: str
    cage_id: str
    direction: str

    def __post_init__(self) -> None:
        if self.direction not in {OUTBOUND, RETURN}:
            raise ValueError(f"invalid transport direction: {self.direction}")

    def to_json(self) -> str:
        return _encode_medical(
            self.task_id,
            self.animal_id,
            self.cage_id,
            event="transport_animal",
            direction=self.direction,
        )

    @classmethod
    def from_json(cls, body: str) -> TransportRequest:
        payload = _decode(body)
        if payload.get("event") != "transport_animal":
            raise MessageContractError("expected transport_animal request")
        direction = _text(payload, "direction")
        if direction not in {OUTBOUND, RETURN}:
            raise MessageContractError(f"invalid transport direction: {direction}")
        return cls(
            _text(payload, "task_id"),
            _text(payload, "animal_id"),
            _text(payload, "cage_id"),
            direction,
        )


@dataclass(frozen=True, slots=True)
class TransportStatus:
    task_id: str
    animal_id: str
    status: str
    reason: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "task_id": self.task_id,
                "animal_id": self.animal_id,
                "status": self.status,
                "reason": self.reason,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, body: str) -> TransportStatus:
        payload = _decode(body)
        status = _text(payload, "status")
        if status not in {
            "accepted",
            "patient_ready",
            "returned",
            "failed",
            "refused",
        }:
            raise MessageContractError(f"invalid transport status: {status}")
        reason = payload.get("reason", "")
        if not isinstance(reason, str):
            raise MessageContractError("reason must be a string")
        return cls(
            _text(payload, "task_id"),
            _text(payload, "animal_id"),
            status,
            reason,
        )


# ============================================================================
# Visualization Frame Contracts
# ============================================================================

@dataclass(frozen=True, slots=True)
class VisualizationUpdate:
    sequence: int
    event: dict[str, Any]
    snapshot: dict[str, Any]
    activity_lines: tuple[str, ...]
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_world(
        cls,
        snapshot: WorldSnapshot,
        event: EnvironmentEvent | None,
        activity_lines: tuple[str, ...] = (),
    ) -> VisualizationUpdate:
        event_payload: dict[str, Any]
        if event is None:
            event_payload = {
                "sequence": 0,
                "action": "initial_state",
                "actor_id": "environment",
                "target_id": "world",
                "task_id": "startup",
                "detail": "simulation initialized",
            }
        else:
            event_payload = {
                "sequence": event.sequence,
                "action": event.action.value,
                "actor_id": event.actor_id,
                "target_id": event.target_id,
                "task_id": event.task_id,
                "detail": event.detail,
                "origin": _pos_dict(event.origin),
                "destination": _pos_dict(event.destination),
                "quantity": event.quantity,
            }
        return cls(
            sequence=event_payload["sequence"],
            event=event_payload,
            snapshot=_snapshot_payload(snapshot),
            activity_lines=activity_lines,
        )

    @classmethod
    def from_rejected_action(
        cls,
        snapshot: WorldSnapshot,
        request: ActionRequest,
        reason: str,
        activity_lines: tuple[str, ...] = (),
    ) -> VisualizationUpdate:
        sequence = snapshot.event_count
        return cls(
            sequence=sequence,
            event={
                "sequence": sequence,
                "action": "action_rejected",
                "requested_action": request.requested_action.value,
                "actor_id": request.actor_id,
                "target_id": request.target_id,
                "task_id": request.task_id,
                "detail": reason,
            },
            snapshot=_snapshot_payload(snapshot),
            activity_lines=activity_lines,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "sequence": self.sequence,
                "event": self.event,
                "snapshot": self.snapshot,
                "activity_lines": list(self.activity_lines),
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, body: str) -> VisualizationUpdate:
        payload = _decode(body)
        sequence = payload.get("sequence")
        event = payload.get("event")
        snapshot = payload.get("snapshot")
        activity_lines = payload.get("activity_lines")
        if type(sequence) is not int or sequence < 0:
            raise MessageContractError("visualization sequence must be non-negative")
        if not isinstance(event, dict) or not isinstance(snapshot, dict):
            raise MessageContractError("visualization event and snapshot must be objects")
        if not isinstance(activity_lines, list) or not all(
            isinstance(line, str) for line in activity_lines
        ):
            raise MessageContractError("visualization activity_lines must be strings")
        return cls(sequence, event, snapshot, tuple(activity_lines))


# ============================================================================
# Private Helpers & Serializers
# ============================================================================

def _encode(task_id: str, cage_id: str, bowl_id: str, event: str) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "cage_id": cage_id,
            "bowl_id": bowl_id,
            "event": event,
        },
        sort_keys=True,
    )


def _encode_medical(
    task_id: str,
    animal_id: str,
    cage_id: str,
    event: str,
    direction: str | None = None,
) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "animal_id": animal_id,
        "cage_id": cage_id,
        "event": event,
    }
    if direction is not None:
        payload["direction"] = direction
    return json.dumps(payload, sort_keys=True)


def _decode(body: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MessageContractError("message body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise MessageContractError("message body must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise MessageContractError("unsupported schema_version")
    return payload


def _text(payload: dict[str, Any], field: str) -> str:
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


def _optional_positive_integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 1:
        raise MessageContractError(f"{field} must be a positive integer")
    return value


def _pos_dict(position: Position | None) -> dict[str, int] | None:
    if position is None:
        return None
    return {"x": position.x, "y": position.y}


def _snapshot_payload(snapshot: WorldSnapshot) -> dict[str, Any]:
    return {
        "width": snapshot.width,
        "height": snapshot.height,
        "areas": [
            {
                "id": area.id,
                "kind": area.kind.value,
                "capacity": area.capacity,
                "cells": [_pos_dict(cell) for cell in sorted(area.cells)],
            }
            for area in snapshot.areas
        ],
        "cages": [
            {
                "id": cage.id,
                "position": _pos_dict(cage.position),
                "animal_id": cage.animal_id,
                "bowl_id": cage.bowl_id,
            }
            for cage in snapshot.cages
        ],
        "bowls": [
            {
                "id": bowl.id,
                "cage_id": bowl.cage_id,
                "position": _pos_dict(bowl.position),
                "level": bowl.level,
                "capacity": bowl.capacity,
            }
            for bowl in snapshot.bowls
        ],
        "animals": [
            {
                "id": animal.id,
                "species": animal.species,
                "condition": animal.condition,
                "cage_id": animal.cage_id,
                "health": animal.health.value,
                "position": _pos_dict(animal.position),
                "carried_by": animal.carried_by,
            }
            for animal in snapshot.animals
        ],
        "agents": [
            {
                "id": agent.id,
                "role": agent.role.value,
                "position": _pos_dict(agent.position),
                "current_task_id": agent.current_task_id,
            }
            for agent in snapshot.agents
        ],
        "tasks": [
            {
                "id": task.id,
                "kind": task.kind.value,
                "target_id": task.target_id,
                "status": task.status.value,
                "assigned_to": task.assigned_to,
            }
            for task in snapshot.tasks
        ],
        "area_access": [
            {
                "area_id": access.area_id,
                "capacity": access.capacity,
                "occupants": list(access.occupants),
                "max_observed": access.max_observed,
            }
            for access in snapshot.area_access
        ],
        "treatment": {
            "patients": list(snapshot.treatment_patients),
            "patient_count": len(snapshot.treatment_patients),
            "patient_capacity": snapshot.treatment_patient_capacity,
            "reserved_count": snapshot.treatment_reserved_count,
            "max_observed": snapshot.max_treatment_patients,
        },
        "max_carried_animals_per_agent": (
            snapshot.max_carried_animals_per_agent
        ),
        "food": [
            {"id": stock.id, "quantity": stock.quantity}
            for stock in snapshot.food_stocks
        ],
        "medicine": [
            {"id": stock.id, "quantity": stock.quantity}
            for stock in snapshot.medicine_stocks
        ],
        "event_count": snapshot.event_count,
    }
