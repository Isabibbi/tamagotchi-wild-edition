"""Contratto SPADE per gli aggiornamenti della visualizzazione."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from tamagotchi_wild.environment import EnvironmentEvent, WorldSnapshot
from tamagotchi_wild.messaging.contracts import (
    SCHEMA_VERSION,
    ActionRequest,
    MessageContractError,
)


VISUALIZATION_ONTOLOGY = "cras.visualization"


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
                "origin": _position(event.origin),
                "destination": _position(event.destination),
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
        """Rappresenta anche un tentativo rifiutato, per mostrare le attese."""

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
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, TypeError) as exc:
            raise MessageContractError("visualization body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise MessageContractError("visualization body must be a JSON object")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise MessageContractError("unsupported visualization schema_version")
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


def _position(position) -> dict[str, int] | None:
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
                "cells": [_position(cell) for cell in sorted(area.cells)],
            }
            for area in snapshot.areas
        ],
        "cages": [
            {
                "id": cage.id,
                "position": _position(cage.position),
                "animal_id": cage.animal_id,
                "bowl_id": cage.bowl_id,
            }
            for cage in snapshot.cages
        ],
        "bowls": [
            {
                "id": bowl.id,
                "cage_id": bowl.cage_id,
                "position": _position(bowl.position),
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
                "position": _position(animal.position),
                "carried_by": animal.carried_by,
            }
            for animal in snapshot.animals
        ],
        "agents": [
            {
                "id": agent.id,
                "role": agent.role.value,
                "position": _position(agent.position),
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
