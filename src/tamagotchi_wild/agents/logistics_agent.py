"""Logistics Agent: trasforma la percezione di una ciotola in un task BDI."""

from __future__ import annotations

import asyncio
from pathlib import Path

import agentspeak as asp
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from tamagotchi_wild.agents.bdi_base import ProjectBDIAgent, term_text
from tamagotchi_wild.messaging import (
    BowlEmptyPerception,
    FEEDING_ONTOLOGY,
    FeedingStatus,
    FeedingTaskRequest,
    MESSAGE_LANGUAGE,
    MessageContractError,
    PERCEPTION_ONTOLOGY,
    workflow_metadata,
)
from tamagotchi_wild.observability import ActivityLog, MessageTrace


DEFAULT_ASL = Path(__file__).parents[1] / "bdi" / "logistics.asl"


class LogisticsAgent(ProjectBDIAgent):
    class PerceptionReceiver(CyclicBehaviour):
        async def run(self) -> None:
            message = await self.receive(timeout=1)
            if message is None:
                return
            try:
                perception = BowlEmptyPerception.from_json(message.body)
                self.agent._validate_conversation(message, perception.task_id)
            except MessageContractError:
                return
            if perception.task_id in self.agent.seen_tasks:
                return
            self.agent.seen_tasks.add(perception.task_id)
            self.agent.bdi.set_belief(
                "bowl_empty",
                perception.task_id,
                perception.cage_id,
                perception.bowl_id,
            )

    class RequestFeeding(CyclicBehaviour):
        def __init__(self, task_id: str, cage_id: str, bowl_id: str) -> None:
            super().__init__()
            self.task_id = task_id
            self.cage_id = cage_id
            self.bowl_id = bowl_id
            self.started = False

        async def run(self) -> None:
            if self.started:
                self.kill()
                return
            self.started = True
            request = FeedingTaskRequest(self.task_id, self.cage_id, self.bowl_id)
            message = _message(
                self.agent.feeding_jid,
                request.to_json(),
                workflow_metadata(FEEDING_ONTOLOGY, "request", self.task_id),
                self.task_id,
            )
            await self.send(message)
            self.agent.message_trace.record(
                self.agent.agent_label,
                self.agent.feeding_jid.split("@", 1)[0],
                FEEDING_ONTOLOGY,
                "request",
                self.task_id,
            )
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                "feeding_requested",
                cage=self.cage_id,
            )

            accepted = await self.receive(timeout=self.agent.timeout_seconds)
            if accepted is None:
                self._set_failed("timeout waiting for task acceptance")
                self.kill()
                return
            try:
                self.agent._validate_conversation(accepted, self.task_id)
                status = FeedingStatus.from_json(accepted.body)
                if (
                    accepted.get_metadata("performative") != "agree"
                    or status.status != "accepted"
                ):
                    self._set_failed(status.reason or "feeding task refused")
                    self.kill()
                    return
            except MessageContractError as exc:
                self._set_failed(str(exc))
                self.kill()
                return

            completed = await self.receive(timeout=self.agent.timeout_seconds)
            if completed is None:
                self._set_failed("timeout waiting for task completion")
                self.kill()
                return
            try:
                self.agent._validate_conversation(completed, self.task_id)
                status = FeedingStatus.from_json(completed.body)
                if (
                    completed.get_metadata("performative") == "inform"
                    and status.status == "completed"
                ):
                    self.agent.bdi.set_belief("feeding_completed", self.task_id)
                else:
                    self._set_failed(status.reason or "feeding task failed")
            except MessageContractError as exc:
                self._set_failed(str(exc))
            self.kill()

        def _set_failed(self, reason: str) -> None:
            self.agent.failure_reasons[self.task_id] = reason
            self.agent.bdi.set_belief("feeding_failed", self.task_id)

    def __init__(
        self,
        jid: str,
        password: str,
        feeding_jid: str,
        activity_log: ActivityLog,
        message_trace: MessageTrace,
        timeout_seconds: float = 10.0,
        asl_file: Path = DEFAULT_ASL,
    ) -> None:
        self.feeding_jid = feeding_jid
        self.activity_log = activity_log
        self.message_trace = message_trace
        self.timeout_seconds = timeout_seconds
        self.agent_label = jid.split("@", 1)[0]
        self.seen_tasks: set[str] = set()
        self.failure_reasons: dict[str, str] = {}
        self.scenario_status: str | None = None
        self.scenario_task_id: str | None = None
        self.scenario_done = asyncio.Event()
        super().__init__(jid, password, str(asl_file))

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "inform")
        template.set_metadata("ontology", PERCEPTION_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.PerceptionReceiver(), template)

    def add_role_actions(self, actions) -> None:
        @actions.add(".request_feeding", 3)
        def request_feeding(agent, term, intention):
            values = [
                term_text(asp.grounded(argument, intention.scope))
                for argument in term.args
            ]
            task_id, cage_id, bowl_id = values
            template = Template()
            template.set_metadata("ontology", FEEDING_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", task_id)
            self.add_behaviour(
                self.RequestFeeding(task_id, cage_id, bowl_id),
                template,
            )
            yield

        @actions.add(".finish_feeding_scenario", 2)
        def finish_feeding_scenario(agent, term, intention):
            task_id = term_text(asp.grounded(term.args[0], intention.scope))
            status = term_text(asp.grounded(term.args[1], intention.scope))
            self.scenario_task_id = task_id
            self.scenario_status = status
            self.scenario_done.set()
            yield

    @staticmethod
    def _validate_conversation(message: Message, task_id: str) -> None:
        if message.get_metadata("conversation-id") != task_id:
            raise MessageContractError("conversation-id does not match task_id")


def _message(
    recipient: str,
    body: str,
    metadata: dict[str, str],
    task_id: str,
) -> Message:
    message = Message(to=recipient, body=body)
    message.thread = task_id
    for key, value in metadata.items():
        message.set_metadata(key, value)
    return message
