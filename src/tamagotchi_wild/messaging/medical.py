
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from tamagotchi_wild.messaging.contracts import (
    SCHEMA_VERSION,
    MessageContractError,
)


TRANSPORT_ONTOLOGY = "cras.transport"
OUTBOUND = "outbound"
RETURN = "return"


@dataclass(frozen=True, slots=True)
class SickAnimalPerception:
    task_id: str
    animal_id: str
    cage_id: str

    def to_json(self) -> str:
        return _encode(
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
        return _encode(
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


def _encode(
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
