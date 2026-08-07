"""Payload e metadata del workflow di alimentazione."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from tamagotchi_wild.messaging.contracts import (
    MESSAGE_LANGUAGE,
    SCHEMA_VERSION,
    MessageContractError,
)


FEEDING_ONTOLOGY = "cras.feeding"
PERCEPTION_ONTOLOGY = "cras.perception"


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
