"""Adattatore SPADE per l'ambiente centralizzato."""

from __future__ import annotations

import asyncio
import json

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template

from tamagotchi_wild.environment import EnvironmentState
from tamagotchi_wild.messaging import (
    ActionRequest,
    ActionResponse,
    BowlEmptyPerception,
    ENVIRONMENT_ONTOLOGY,
    MESSAGE_LANGUAGE,
    MessageContractError,
    PERCEPTION_ONTOLOGY,
    SickAnimalPerception,
    workflow_metadata,
)
from tamagotchi_wild.domain import ActionType
from tamagotchi_wild.observability import ActivityLog, MessageTrace


def process_action_request(world: EnvironmentState, body: str) -> ActionResponse:
    """Validate one JSON request and delegate the state change to the world."""

    try:
        request = ActionRequest.from_json(body)
    except MessageContractError as exc:
        return ActionResponse(
            task_id="unknown",
            accepted=False,
            reason=str(exc),
            event_sequence=None,
        )
    return ActionResponse.from_result(request.task_id, world.apply(request.to_command()))


class EnvironmentAgent(Agent):
    """SPADE boundary; the authoritative state remains independently testable."""

    class RequestBehaviour(CyclicBehaviour):
        async def run(self) -> None:
            message = await self.receive(timeout=1)
            if message is None:
                return

            request = None
            try:
                request = ActionRequest.from_json(message.body)
            except MessageContractError:
                pass
            response_data = process_action_request(self.agent.world, message.body)
            response = Message(to=str(message.sender))
            conversation_id = message.get_metadata("conversation-id")
            response.thread = message.thread or conversation_id
            response.set_metadata(
                "performative", "inform" if response_data.accepted else "failure"
            )
            response.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
            response.set_metadata("language", MESSAGE_LANGUAGE)
            if conversation_id:
                response.set_metadata("conversation-id", conversation_id)
            response.body = response_data.to_json()
            await self.send(response)
            self.agent.message_trace.record(
                self.agent.agent_label,
                str(message.sender).split("@", 1)[0],
                ENVIRONMENT_ONTOLOGY,
                "inform" if response_data.accepted else "failure",
                conversation_id or response_data.task_id,
            )
            if request is not None and response_data.accepted:
                self.agent._record_action(request)

    class PerceptionSender(OneShotBehaviour):
        def __init__(
            self,
            recipient: str,
            perception: BowlEmptyPerception,
            sent: asyncio.Event,
        ) -> None:
            super().__init__()
            self.recipient = recipient
            self.perception = perception
            self.sent = sent

        async def run(self) -> None:
            task_id = self.perception.task_id
            message = Message(to=self.recipient, body=self.perception.to_json())
            message.thread = task_id
            for key, value in workflow_metadata(
                PERCEPTION_ONTOLOGY,
                "inform",
                task_id,
            ).items():
                message.set_metadata(key, value)
            await self.send(message)
            self.agent.message_trace.record(
                self.agent.agent_label,
                self.recipient.split("@", 1)[0],
                PERCEPTION_ONTOLOGY,
                "inform",
                task_id,
            )
            self.sent.set()

    class SickAnimalSender(OneShotBehaviour):
        def __init__(
            self,
            recipient: str,
            perception: SickAnimalPerception,
            sent: asyncio.Event,
        ) -> None:
            super().__init__()
            self.recipient = recipient
            self.perception = perception
            self.sent = sent

        async def run(self) -> None:
            task_id = self.perception.task_id
            message = Message(to=self.recipient, body=self.perception.to_json())
            message.thread = task_id
            for key, value in workflow_metadata(
                PERCEPTION_ONTOLOGY,
                "inform",
                task_id,
            ).items():
                message.set_metadata(key, value)
            await self.send(message)
            self.agent.message_trace.record(
                self.agent.agent_label,
                self.recipient.split("@", 1)[0],
                PERCEPTION_ONTOLOGY,
                "inform",
                task_id,
            )
            self.sent.set()

    def __init__(
        self,
        jid: str,
        password: str,
        world: EnvironmentState,
        activity_log: ActivityLog | None = None,
        message_trace: MessageTrace | None = None,
    ) -> None:
        self.world = world
        self.activity_log = activity_log or ActivityLog()
        self.message_trace = message_trace or MessageTrace()
        self.agent_label = jid.split("@", 1)[0]
        super().__init__(jid, password)

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "request")
        template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.RequestBehaviour(), template)

    async def publish_bowl_empty(
        self,
        recipient: str,
        task_id: str,
        cage_id: str,
        bowl_id: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        sent = asyncio.Event()
        self.add_behaviour(
            self.PerceptionSender(
                recipient,
                BowlEmptyPerception(task_id, cage_id, bowl_id),
                sent,
            )
        )
        await asyncio.wait_for(sent.wait(), timeout=timeout_seconds)

    async def publish_sick_animal(
        self,
        recipient: str,
        task_id: str,
        animal_id: str,
        cage_id: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        sent = asyncio.Event()
        self.add_behaviour(
            self.SickAnimalSender(
                recipient,
                SickAnimalPerception(task_id, animal_id, cage_id),
                sent,
            )
        )
        await asyncio.wait_for(sent.wait(), timeout=timeout_seconds)

    def _record_action(self, request: ActionRequest) -> None:
        if request.requested_action is ActionType.TAKE_FOOD:
            self.activity_log.record(
                request.task_id,
                self.agent_label,
                "food_taken",
                quantity=request.quantity,
            )
        elif request.requested_action is ActionType.FILL_BOWL:
            snapshot = self.world.snapshot()
            bowl = next(
                (item for item in snapshot.bowls if item.id == request.target_id),
                None,
            )
            details = {"bowl": request.target_id}
            if bowl is not None:
                details = {"cage": bowl.cage_id}
            self.activity_log.record(
                request.task_id,
                self.agent_label,
                "bowl_filled",
                **details,
            )
        elif request.requested_action is ActionType.FAIL_TASK:
            self.activity_log.record(
                request.task_id,
                self.agent_label,
                "task_rejected",
            )
        elif request.requested_action in {
            ActionType.PICKUP_SICK_ANIMAL,
            ActionType.DELIVER_TO_TREATMENT,
            ActionType.TAKE_MEDICINE,
            ActionType.TREAT_ANIMAL,
            ActionType.PICKUP_TREATED_ANIMAL,
            ActionType.RETURN_ANIMAL_TO_CAGE,
        }:
            event_by_action = {
                ActionType.PICKUP_SICK_ANIMAL: "patient_picked_up",
                ActionType.DELIVER_TO_TREATMENT: "patient_delivered",
                ActionType.TAKE_MEDICINE: "medicine_taken",
                ActionType.TREAT_ANIMAL: "animal_treated",
                ActionType.PICKUP_TREATED_ANIMAL: "treated_patient_picked_up",
                ActionType.RETURN_ANIMAL_TO_CAGE: "patient_returned",
            }
            self.activity_log.record(
                request.task_id,
                self.agent_label,
                event_by_action[request.requested_action],
                target=request.target_id,
            )
