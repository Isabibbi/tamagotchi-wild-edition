"""Logistics Agent: gestisce task di alimentazione e trasporto medico."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Mapping, Sequence

import agentspeak as asp
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

from tamagotchi_wild.agents.bdi_base import ProjectBDIAgent, term_text
from tamagotchi_wild.agents.environment_actions import (
    acquire_area,
    claim_task,
    environment_action,
    release_area,
)
from tamagotchi_wild.domain import ActionType, Position
from tamagotchi_wild.messaging import (
    ActionResponse,
    BowlEmptyPerception,
    ENVIRONMENT_ONTOLOGY,
    FEEDING_ONTOLOGY,
    FeedingStatus,
    FeedingTaskRequest,
    MESSAGE_LANGUAGE,
    MessageContractError,
    PERCEPTION_ONTOLOGY,
    TRANSPORT_ONTOLOGY,
    TransportRequest,
    TransportStatus,
    OUTBOUND,
    RETURN,
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
            template = Template()
            template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", perception.task_id)
            self.agent.add_behaviour(
                self.agent.ClaimFeedingCoordination(perception),
                template,
            )

    class ClaimFeedingCoordination(OneShotBehaviour):
        def __init__(self, perception: BowlEmptyPerception) -> None:
            super().__init__()
            self.perception = perception

        async def run(self) -> None:
            result = await claim_task(
                self,
                self.perception.task_id,
                "feeding_coordination",
            )
            if result.accepted:
                self.agent.bdi.set_belief(
                    "bowl_empty",
                    self.perception.task_id,
                    self.perception.cage_id,
                    self.perception.bowl_id,
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
            self.recipients = (
                _round_robin_recipient(self.agent.feeding_jids, self.task_id),
            )
            for feeding_jid in self.recipients:
                message = _message(
                    feeding_jid,
                    request.to_json(),
                    workflow_metadata(FEEDING_ONTOLOGY, "request", self.task_id),
                    self.task_id,
                )
                await self.send(message)
                self.agent.message_trace.record(
                    self.agent.agent_label,
                    feeding_jid.split("@", 1)[0],
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

            winner = await self._wait_for_winner()
            if winner is None:
                self._set_failed("timeout waiting for task acceptance")
                self.kill()
                return

            completed = await self._wait_for_completion(winner)
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

        async def _wait_for_winner(self) -> str | None:
            deadline = asyncio.get_running_loop().time() + self.agent.timeout_seconds
            refusals: set[str] = set()
            while len(refusals) < len(self.recipients):
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return None
                message = await self.receive(timeout=remaining)
                if message is None:
                    return None
                try:
                    self.agent._validate_conversation(message, self.task_id)
                    status = FeedingStatus.from_json(message.body)
                except MessageContractError:
                    continue
                sender = str(message.sender).split("/", 1)[0]
                if (
                    message.get_metadata("performative") == "agree"
                    and status.status == "accepted"
                ):
                    return sender
                if message.get_metadata("performative") == "refuse":
                    refusals.add(sender)
            return None

        async def _wait_for_completion(self, winner: str) -> Message | None:
            deadline = asyncio.get_running_loop().time() + self.agent.timeout_seconds
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return None
                message = await self.receive(timeout=remaining)
                if message is None:
                    return None
                sender = str(message.sender).split("/", 1)[0]
                if sender == winner:
                    return message

        def _set_failed(self, reason: str) -> None:
            self.agent.failure_reasons[self.task_id] = reason
            self.agent.bdi.set_belief("feeding_failed", self.task_id)

    class TransportReceiver(CyclicBehaviour):
        async def run(self) -> None:
            message = await self.receive(timeout=1)
            if message is None:
                return
            try:
                request = TransportRequest.from_json(message.body)
                self.agent._validate_conversation(message, request.task_id)
            except MessageContractError:
                return
            key = (request.task_id, request.direction)
            if key in self.agent.seen_transport_requests:
                return
            self.agent.seen_transport_requests.add(key)
            self.agent.transport_requesters[key] = str(message.sender)
            template = Template()
            template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", request.task_id)
            self.agent.add_behaviour(
                self.agent.ClaimTransport(request),
                template,
            )

    class ClaimTransport(OneShotBehaviour):
        def __init__(self, request: TransportRequest) -> None:
            super().__init__()
            self.request = request

        async def run(self) -> None:
            phase = f"transport_{self.request.direction}"
            result = await claim_task(self, self.request.task_id, phase)
            if result.accepted:
                self.agent.bdi.set_belief(
                    "transport_requested",
                    self.request.task_id,
                    self.request.animal_id,
                    self.request.cage_id,
                    self.request.direction,
                )
                return

            requester = self.agent.transport_requesters[
                (self.request.task_id, self.request.direction)
            ]
            status = TransportStatus(
                self.request.task_id,
                self.request.animal_id,
                "refused",
                result.reason,
            )
            message = _message(
                requester,
                status.to_json(),
                workflow_metadata(
                    TRANSPORT_ONTOLOGY,
                    "refuse",
                    self.request.task_id,
                ),
                self.request.task_id,
            )
            await self.send(message)
            self.agent.message_trace.record(
                self.agent.agent_label,
                requester.split("@", 1)[0],
                TRANSPORT_ONTOLOGY,
                "refuse",
                self.request.task_id,
            )

    class ExecuteTransport(CyclicBehaviour):
        def __init__(
            self,
            task_id: str,
            animal_id: str,
            cage_id: str,
            direction: str,
        ) -> None:
            super().__init__()
            self.task_id = task_id
            self.animal_id = animal_id
            self.cage_id = cage_id
            self.direction = direction
            self.started = False

        async def run(self) -> None:
            if self.started:
                self.kill()
                return
            self.started = True
            requester = self.agent.transport_requesters[
                (self.task_id, self.direction)
            ]
            await self._send_status(requester, "agree", "accepted")
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                "transport_accepted",
                direction=self.direction,
            )

            if self.direction == OUTBOUND:
                cage_position = self.agent.cage_positions.get(
                    self.cage_id,
                    self.agent.cage_position,
                )
                actions = (
                    (
                        self.agent.cage_area_id,
                        cage_position,
                        ActionType.PICKUP_SICK_ANIMAL,
                        None,
                    ),
                    (
                        self.agent.treatment_area_id,
                        self.agent.treatment_position,
                        ActionType.DELIVER_TO_TREATMENT,
                        self.agent.treatment_position,
                    ),
                )
                final_status = "patient_ready"
            else:
                cage_position = self.agent.cage_positions.get(
                    self.cage_id,
                    self.agent.cage_position,
                )
                actions = (
                    (
                        self.agent.treatment_area_id,
                        self.agent.treatment_position,
                        ActionType.PICKUP_TREATED_ANIMAL,
                        None,
                    ),
                    (
                        self.agent.cage_area_id,
                        cage_position,
                        ActionType.RETURN_ANIMAL_TO_CAGE,
                        cage_position,
                    ),
                )
                final_status = "returned"

            for area_id, access_position, action, destination in actions:
                result = await self._perform_in_area(
                    area_id,
                    access_position,
                    action,
                    destination,
                )
                if not result.accepted:
                    await self._send_status(
                        requester,
                        "failure",
                        "failed",
                        result.reason,
                    )
                    self.agent.transport_failures[self.task_id] = result.reason
                    self.kill()
                    return

            await self._send_status(requester, "inform", final_status)
            self.agent.transport_outcomes[
                (self.task_id, self.direction)
            ] = final_status
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                final_status,
                animal=self.animal_id,
            )
            self.kill()

        async def _perform_in_area(
            self,
            area_id: str,
            access_position: Position,
            action: ActionType,
            destination: Position | None,
        ) -> ActionResponse:
            access = await acquire_area(
                self,
                self.task_id,
                area_id,
                access_position,
            )
            if not access.accepted:
                return access
            result = await environment_action(
                self,
                self.task_id,
                action,
                self.animal_id,
                destination=destination,
            )
            released = await release_area(self, self.task_id, area_id)
            return result if released.accepted else released

        async def _send_status(
            self,
            recipient: str,
            performative: str,
            status: str,
            reason: str = "",
        ) -> None:
            body = TransportStatus(
                self.task_id,
                self.animal_id,
                status,
                reason,
            ).to_json()
            message = _message(
                recipient,
                body,
                workflow_metadata(
                    TRANSPORT_ONTOLOGY,
                    performative,
                    self.task_id,
                ),
                self.task_id,
            )
            await self.send(message)
            self.agent.message_trace.record(
                self.agent.agent_label,
                recipient.split("@", 1)[0],
                TRANSPORT_ONTOLOGY,
                performative,
                self.task_id,
            )

    def __init__(
        self,
        jid: str,
        password: str,
        feeding_jid: str | Sequence[str],
        activity_log: ActivityLog,
        message_trace: MessageTrace,
        timeout_seconds: float = 10.0,
        asl_file: Path = DEFAULT_ASL,
        environment_jid: str = "environment@localhost",
        cage_position: Position = Position(2, 4),
        treatment_position: Position = Position(9, 4),
        cage_area_id: str = "cage-area",
        treatment_area_id: str = "treatment-room",
        cage_positions: Mapping[str, Position] | None = None,
    ) -> None:
        self.feeding_jids = (
            (feeding_jid,) if isinstance(feeding_jid, str) else tuple(feeding_jid)
        )
        if not self.feeding_jids:
            raise ValueError("at least one Feeding Agent JID is required")
        self.feeding_jid = self.feeding_jids[0]
        self.activity_log = activity_log
        self.message_trace = message_trace
        self.timeout_seconds = timeout_seconds
        self.agent_label = jid.split("@", 1)[0]
        self.environment_jid = environment_jid
        self.cage_position = cage_position
        self.cage_positions = dict(cage_positions or {})
        self.treatment_position = treatment_position
        self.cage_area_id = cage_area_id
        self.treatment_area_id = treatment_area_id
        self.seen_tasks: set[str] = set()
        self.failure_reasons: dict[str, str] = {}
        self.workflow_status: str | None = None
        self.workflow_task_id: str | None = None
        self.workflow_done = asyncio.Event()
        self.workflow_outcomes: dict[str, str] = {}
        self.seen_transport_requests: set[tuple[str, str]] = set()
        self.transport_requesters: dict[tuple[str, str], str] = {}
        self.transport_outcomes: dict[tuple[str, str], str] = {}
        self.transport_failures: dict[str, str] = {}
        super().__init__(jid, password, str(asl_file))

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "inform")
        template.set_metadata("ontology", PERCEPTION_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.PerceptionReceiver(), template)
        transport_template = Template()
        transport_template.set_metadata("performative", "request")
        transport_template.set_metadata("ontology", TRANSPORT_ONTOLOGY)
        transport_template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.TransportReceiver(), transport_template)

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

        @actions.add(".finish_feeding_workflow", 2)
        def finish_feeding_workflow(agent, term, intention):
            task_id = term_text(asp.grounded(term.args[0], intention.scope))
            status = term_text(asp.grounded(term.args[1], intention.scope))
            self.workflow_task_id = task_id
            self.workflow_status = status
            self.workflow_outcomes[task_id] = status
            self.workflow_done.set()
            yield

        @actions.add(".execute_transport", 4)
        def execute_transport(agent, term, intention):
            values = [
                term_text(asp.grounded(argument, intention.scope))
                for argument in term.args
            ]
            task_id, animal_id, cage_id, direction = values
            template = Template()
            template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", task_id)
            self.add_behaviour(
                self.ExecuteTransport(task_id, animal_id, cage_id, direction),
                template,
            )
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


def _round_robin_recipient(jids: Sequence[str], task_id: str) -> str:
    try:
        task_number = int(task_id.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        task_number = 1
    return jids[(task_number - 1) % len(jids)]
