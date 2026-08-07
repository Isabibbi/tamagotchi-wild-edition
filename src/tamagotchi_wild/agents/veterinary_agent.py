"""Veterinary Agent: coordina trasporto, cura e rientro del paziente."""

from __future__ import annotations

import asyncio
from pathlib import Path

import agentspeak as asp
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from tamagotchi_wild.agents.bdi_base import ProjectBDIAgent, term_text
from tamagotchi_wild.domain import ActionType, Position
from tamagotchi_wild.messaging import (
    ActionRequest,
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
    request_metadata,
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
            self.agent.bdi.set_belief(
                "sick_animal",
                perception.task_id,
                perception.animal_id,
                perception.cage_id,
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
            message = _message(
                self.agent.logistics_jid,
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
                self.agent.logistics_jid,
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

            accepted = await self.receive(timeout=self.agent.timeout_seconds)
            if accepted is None:
                self._fail("timeout waiting for transport acceptance")
                self.kill()
                return
            try:
                self.agent._validate_conversation(accepted, self.task_id)
                status = TransportStatus.from_json(accepted.body)
                if (
                    accepted.get_metadata("performative") != "agree"
                    or status.status != "accepted"
                ):
                    self._fail(status.reason or "transport refused")
                    self.kill()
                    return
            except MessageContractError as exc:
                self._fail(str(exc))
                self.kill()
                return

            result_message = await self.receive(timeout=self.agent.timeout_seconds)
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
                    ActionType.TAKE_MEDICINE,
                    self.agent.medicine_stock_id,
                    None,
                    1,
                ),
                (
                    ActionType.MOVE_AGENT,
                    self.agent.agent_label,
                    self.agent.treatment_position,
                    None,
                ),
                (ActionType.TREAT_ANIMAL, self.animal_id, None, None),
            )
            for action, target_id, destination, quantity in operations:
                result = await self._environment_action(
                    action,
                    target_id,
                    destination,
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

        async def _environment_action(
            self,
            action: ActionType,
            target_id: str,
            destination: Position | None,
            quantity: int | None,
        ) -> ActionResponse:
            request = ActionRequest(
                task_id=self.task_id,
                actor_id=self.agent.agent_label,
                target_id=target_id,
                requested_action=action,
                destination=destination,
                quantity=quantity,
            )
            message = _message(
                self.agent.environment_jid,
                request.to_json(),
                request_metadata(self.task_id),
                self.task_id,
            )
            await self.send(message)
            self.agent._trace_message(
                self.agent.environment_jid,
                ENVIRONMENT_ONTOLOGY,
                "request",
                self.task_id,
            )
            response = await self.receive(timeout=self.agent.timeout_seconds)
            if response is None:
                return ActionResponse(
                    self.task_id,
                    False,
                    f"timeout waiting for {action.value}",
                    None,
                )
            try:
                self.agent._validate_conversation(response, self.task_id)
                parsed = ActionResponse.from_json(response.body)
                if parsed.task_id != self.task_id:
                    raise MessageContractError("response task_id does not match")
                return parsed
            except MessageContractError as exc:
                return ActionResponse(self.task_id, False, str(exc), None)

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
            request = ActionRequest(
                task_id=self.task_id,
                actor_id=self.agent.agent_label,
                target_id=self.task_id,
                requested_action=ActionType.FAIL_TASK,
            )
            message = _message(
                self.agent.environment_jid,
                request.to_json(),
                request_metadata(self.task_id),
                self.task_id,
            )
            await self.send(message)
            self.agent._trace_message(
                self.agent.environment_jid,
                ENVIRONMENT_ONTOLOGY,
                "request",
                self.task_id,
            )
            await self.receive(timeout=self.agent.timeout_seconds)
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
        logistics_jid: str,
        environment_jid: str,
        medicine_stock_id: str,
        treatment_position: Position,
        activity_log: ActivityLog,
        message_trace: MessageTrace,
        timeout_seconds: float = 10.0,
        asl_file: Path = DEFAULT_ASL,
    ) -> None:
        self.logistics_jid = logistics_jid
        self.environment_jid = environment_jid
        self.medicine_stock_id = medicine_stock_id
        self.treatment_position = treatment_position
        self.activity_log = activity_log
        self.message_trace = message_trace
        self.timeout_seconds = timeout_seconds
        self.agent_label = jid.split("@", 1)[0]
        self.seen_tasks: set[str] = set()
        self.failure_reasons: dict[str, str] = {}
        self.rejection_started: set[str] = set()
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

        @actions.add(".finish_medical_scenario", 2)
        def finish_medical_scenario(agent, term, intention):
            task_id = term_text(asp.grounded(term.args[0], intention.scope))
            status = term_text(asp.grounded(term.args[1], intention.scope))
            self.scenario_task_id = task_id
            self.scenario_status = status
            self.scenario_done.set()
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
