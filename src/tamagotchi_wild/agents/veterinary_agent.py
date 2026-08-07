"""Veterinary Agent: coordina trasporto, cura e rientro del paziente."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Sequence

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
    ENVIRONMENT_ONTOLOGY,
    MESSAGE_LANGUAGE,
    MessageContractError,
    OUTBOUND,
    PERCEPTION_ONTOLOGY,
    RETURN,
    SickAnimalPerception,
    TRANSPORT_ONTOLOGY,
    TransportRequest,
    TransportStatus,
    workflow_metadata,
)
from tamagotchi_wild.observability import ActivityLog, MessageTrace


DEFAULT_ASL = Path(__file__).parents[1] / "bdi" / "veterinary.asl"


class VeterinaryAgent(ProjectBDIAgent):
    class PerceptionReceiver(CyclicBehaviour):
        async def run(self) -> None:
            message = await self.receive(timeout=1)
            if message is None:
                return
            try:
                perception = SickAnimalPerception.from_json(message.body)
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
                self.agent.ClaimMedicalCoordination(perception),
                template,
            )

    class ClaimMedicalCoordination(OneShotBehaviour):
        def __init__(self, perception: SickAnimalPerception) -> None:
            super().__init__()
            self.perception = perception

        async def run(self) -> None:
            result = await claim_task(
                self,
                self.perception.task_id,
                "medical_coordination",
            )
            if result.accepted:
                self.agent.bdi.set_belief(
                    "sick_animal",
                    self.perception.task_id,
                    self.perception.animal_id,
                    self.perception.cage_id,
                )

    class RequestTransport(CyclicBehaviour):
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
            request = TransportRequest(
                self.task_id,
                self.animal_id,
                self.cage_id,
                self.direction,
            )
            for logistics_jid in self.agent.logistics_jids:
                message = _message(
                    logistics_jid,
                    request.to_json(),
                    workflow_metadata(
                        TRANSPORT_ONTOLOGY,
                        "request",
                        self.task_id,
                    ),
                    self.task_id,
                )
                await self.send(message)
                self.agent._trace_message(
                    logistics_jid,
                    TRANSPORT_ONTOLOGY,
                    "request",
                    self.task_id,
                )
            event = (
                "outbound_transport_requested"
                if self.direction == OUTBOUND
                else "return_transport_requested"
            )
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                event,
                animal=self.animal_id,
            )

            winner = await self._wait_for_winner()
            if winner is None:
                self._fail("timeout waiting for transport acceptance")
                self.kill()
                return

            result_message = await self._wait_for_completion(winner)
            if result_message is None:
                self._fail("timeout waiting for transport completion")
                self.kill()
                return
            try:
                self.agent._validate_conversation(result_message, self.task_id)
                status = TransportStatus.from_json(result_message.body)
                expected = "patient_ready" if self.direction == OUTBOUND else "returned"
                if (
                    result_message.get_metadata("performative") == "inform"
                    and status.status == expected
                ):
                    belief = "patient_ready" if self.direction == OUTBOUND else "animal_returned"
                    self.agent.bdi.set_belief(
                        belief,
                        self.task_id,
                        self.animal_id,
                        self.cage_id,
                    )
                else:
                    self._fail(status.reason or "transport failed")
            except MessageContractError as exc:
                self._fail(str(exc))
            self.kill()

        async def _wait_for_winner(self) -> str | None:
            deadline = asyncio.get_running_loop().time() + self.agent.timeout_seconds
            refusals: set[str] = set()
            while len(refusals) < len(self.agent.logistics_jids):
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return None
                message = await self.receive(timeout=remaining)
                if message is None:
                    return None
                try:
                    self.agent._validate_conversation(message, self.task_id)
                    status = TransportStatus.from_json(message.body)
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

        def _fail(self, reason: str) -> None:
            self.agent.reject_task(self.task_id, self.animal_id, reason)

    class ExecuteTreatment(CyclicBehaviour):
        def __init__(
            self,
            task_id: str,
            animal_id: str,
            cage_id: str,
        ) -> None:
            super().__init__()
            self.task_id = task_id
            self.animal_id = animal_id
            self.cage_id = cage_id
            self.started = False

        async def run(self) -> None:
            if self.started:
                self.kill()
                return
            self.started = True
            operations = (
                (
                    self.agent.medical_area_id,
                    self.agent.medicine_position,
                    ActionType.TAKE_MEDICINE,
                    self.agent.medicine_stock_id,
                    1,
                ),
                (
                    self.agent.treatment_area_id,
                    self.agent.treatment_position,
                    ActionType.TREAT_ANIMAL,
                    self.animal_id,
                    None,
                ),
            )
            for area_id, access_position, action, target_id, quantity in operations:
                result = await self._perform_in_area(
                    area_id,
                    access_position,
                    action,
                    target_id,
                    quantity,
                )
                if not result.accepted:
                    self.agent.reject_task(
                        self.task_id,
                        self.animal_id,
                        result.reason,
                    )
                    self.kill()
                    return

            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                "treatment_completed",
                animal=self.animal_id,
            )
            self.agent.bdi.set_belief(
                "treatment_succeeded",
                self.task_id,
                self.animal_id,
                self.cage_id,
            )
            self.kill()

        async def _perform_in_area(
            self,
            area_id: str,
            access_position: Position,
            action: ActionType,
            target_id: str,
            quantity: int | None,
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
                target_id,
                quantity=quantity,
            )
            released = await release_area(self, self.task_id, area_id)
            return result if released.accepted else released

    class RejectTask(CyclicBehaviour):
        def __init__(self, task_id: str, animal_id: str, reason: str) -> None:
            super().__init__()
            self.task_id = task_id
            self.animal_id = animal_id
            self.reason = reason
            self.started = False

        async def run(self) -> None:
            if self.started:
                self.kill()
                return
            self.started = True
            await environment_action(
                self,
                self.task_id,
                ActionType.FAIL_TASK,
                self.task_id,
            )
            self.agent.failure_reasons[self.task_id] = self.reason
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                "medical_task_failed",
                reason=self.reason.replace(" ", "_"),
            )
            self.agent.bdi.set_belief("medical_failed", self.task_id)
            self.kill()

    def __init__(
        self,
        jid: str,
        password: str,
        logistics_jid: str | Sequence[str],
        environment_jid: str,
        medicine_stock_id: str,
        treatment_position: Position,
        activity_log: ActivityLog,
        message_trace: MessageTrace,
        timeout_seconds: float = 10.0,
        asl_file: Path = DEFAULT_ASL,
        medicine_position: Position = Position(6, 1),
        medical_area_id: str = "medical-storage",
        treatment_area_id: str = "treatment-room",
    ) -> None:
        self.logistics_jids = (
            (logistics_jid,) if isinstance(logistics_jid, str) else tuple(logistics_jid)
        )
        if not self.logistics_jids:
            raise ValueError("at least one Logistics Agent JID is required")
        self.logistics_jid = self.logistics_jids[0]
        self.environment_jid = environment_jid
        self.medicine_stock_id = medicine_stock_id
        self.treatment_position = treatment_position
        self.medicine_position = medicine_position
        self.medical_area_id = medical_area_id
        self.treatment_area_id = treatment_area_id
        self.activity_log = activity_log
        self.message_trace = message_trace
        self.timeout_seconds = timeout_seconds
        self.agent_label = jid.split("@", 1)[0]
        self.seen_tasks: set[str] = set()
        self.failure_reasons: dict[str, str] = {}
        self.rejection_started: set[str] = set()
        self.workflow_status: str | None = None
        self.workflow_task_id: str | None = None
        self.workflow_done = asyncio.Event()
        super().__init__(jid, password, str(asl_file))

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "inform")
        template.set_metadata("ontology", PERCEPTION_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.PerceptionReceiver(), template)

    def add_role_actions(self, actions) -> None:
        @actions.add(".request_medical_transport", 4)
        def request_medical_transport(agent, term, intention):
            values = [
                term_text(asp.grounded(argument, intention.scope))
                for argument in term.args
            ]
            task_id, animal_id, cage_id, direction = values
            template = Template()
            template.set_metadata("ontology", TRANSPORT_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", task_id)
            self.add_behaviour(
                self.RequestTransport(task_id, animal_id, cage_id, direction),
                template,
            )
            yield

        @actions.add(".execute_medical_treatment", 3)
        def execute_medical_treatment(agent, term, intention):
            values = [
                term_text(asp.grounded(argument, intention.scope))
                for argument in term.args
            ]
            task_id, animal_id, cage_id = values
            template = Template()
            template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", task_id)
            self.add_behaviour(
                self.ExecuteTreatment(task_id, animal_id, cage_id),
                template,
            )
            yield

        @actions.add(".finish_medical_workflow", 2)
        def finish_medical_workflow(agent, term, intention):
            task_id = term_text(asp.grounded(term.args[0], intention.scope))
            status = term_text(asp.grounded(term.args[1], intention.scope))
            self.workflow_task_id = task_id
            self.workflow_status = status
            self.workflow_done.set()
            yield

    def reject_task(self, task_id: str, animal_id: str, reason: str) -> None:
        if task_id in self.rejection_started:
            return
        self.rejection_started.add(task_id)
        template = Template()
        template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        template.set_metadata("conversation-id", task_id)
        self.add_behaviour(self.RejectTask(task_id, animal_id, reason), template)

    def _trace_message(
        self,
        recipient: str,
        ontology: str,
        performative: str,
        task_id: str,
    ) -> None:
        self.message_trace.record(
            self.agent_label,
            recipient.split("@", 1)[0],
            ontology,
            performative,
            task_id,
        )

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
