"""Log leggibili e tracce dei messaggi per scenari e test."""

from __future__ import annotations

from dataclasses import dataclass


class ActivityLog:
    def __init__(self) -> None:
        self._lines: list[str] = []

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self._lines)

    def record(self, task_id: str, agent: str, event: str, **details: object) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in details.items())
        line = f"task={task_id} agent={agent} event={event}"
        if suffix:
            line = f"{line} {suffix}"
        self._lines.append(line)


@dataclass(frozen=True, slots=True)
class MessageRecord:
    sender: str
    recipient: str
    ontology: str
    performative: str
    conversation_id: str


class MessageTrace:
    def __init__(self) -> None:
        self._records: list[MessageRecord] = []

    @property
    def records(self) -> tuple[MessageRecord, ...]:
        return tuple(self._records)

    def record(
        self,
        sender: str,
        recipient: str,
        ontology: str,
        performative: str,
        conversation_id: str,
    ) -> None:
        self._records.append(
            MessageRecord(
                sender,
                recipient,
                ontology,
                performative,
                conversation_id,
            )
        )
