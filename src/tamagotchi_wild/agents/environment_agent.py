
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
    VISUALIZATION_ONTOLOGY,
    VisualizationUpdate,
    workflow_metadata,
)
from tamagotchi_wild.domain import ActionType
from tamagotchi_wild.observability import ActivityLog, MessageTrace


def process_action_request(world: EnvironmentState, body: str) -> ActionResponse:

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
                self.agent._clear_visualization_rejection(request)
                self.agent._record_action(request)
                if response_data.event_sequence is not None:
                    await self.agent._send_visualization_update(
                        self,
                        response_data.event_sequence,
                    )
            elif (
                request is not None
                and self.agent.visualization_jid is not None
                and self.agent._should_publish_visualization_rejection(
                    request,
                    response_data.reason,
                )
            ):
                await self.agent._send_visualization_rejection(
                    self,
                    request,
                    response_data.reason,
                )

    class VisualStateSender(OneShotBehaviour):
        def __init__(self, sent: asyncio.Event) -> None:
            super().__init__()
            self.sent = sent

        async def run(self) -> None:
            await self.agent._send_visualization_update(self, None)
            self.sent.set()

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
        visualization_jid: str | None = None,
    ) -> None:
        self.world = world
        self.activity_log = activity_log or ActivityLog()
        self.message_trace = message_trace or MessageTrace()
        self.agent_label = jid.split("@", 1)[0]
        self.visualization_jid = visualization_jid
        self._active_visualization_rejections: set[
            tuple[str, str, ActionType, str, str]
        ] = set()
        super().__init__(jid, password)

    def _should_publish_visualization_rejection(
        self,
        request: ActionRequest,
        reason: str,
    ) -> bool:
        rejection = (
            request.task_id,
            request.actor_id,
            request.requested_action,
            request.target_id,
            reason,
        )
        if rejection in self._active_visualization_rejections:
            return False
        self._active_visualization_rejections.add(rejection)
        return True

    def _clear_visualization_rejection(self, request: ActionRequest) -> None:
        identity = (
            request.task_id,
            request.actor_id,
            request.requested_action,
            request.target_id,
        )
        self._active_visualization_rejections = {
            rejection
            for rejection in self._active_visualization_rejections
            if rejection[:4] != identity
        }

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

    async def publish_initial_visual_state(
        self,
        timeout_seconds: float = 5.0,
    ) -> None:
        if self.visualization_jid is None:
            return
        sent = asyncio.Event()
        self.add_behaviour(self.VisualStateSender(sent))
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

    async def _send_visualization_update(
        self,
        behaviour,
        event_sequence: int | None,
    ) -> None:
        if self.visualization_jid is None:
            return
        event = None
        if event_sequence is not None:
            event = next(
                (
                    item
                    for item in self.world.events
                    if item.sequence == event_sequence
                ),
                None,
            )
        update = VisualizationUpdate.from_world(
            self.world.snapshot(),
            event,
            self.activity_log.lines,
        )
        conversation_id = f"visual-{update.sequence:06d}"
        message = Message(to=self.visualization_jid, body=update.to_json())
        message.thread = conversation_id
        message.set_metadata("performative", "inform")
        message.set_metadata("ontology", VISUALIZATION_ONTOLOGY)
        message.set_metadata("language", MESSAGE_LANGUAGE)
        message.set_metadata("conversation-id", conversation_id)
        await behaviour.send(message)
        self.message_trace.record(
            self.agent_label,
            self.visualization_jid.split("@", 1)[0],
            VISUALIZATION_ONTOLOGY,
            "inform",
            conversation_id,
        )

    async def _send_visualization_rejection(
        self,
        behaviour,
        request: ActionRequest,
        reason: str,
    ) -> None:
        if self.visualization_jid is None:
            return
        update = VisualizationUpdate.from_rejected_action(
            self.world.snapshot(),
            request,
            reason,
            self.activity_log.lines,
        )
        conversation_id = f"visual-wait-{request.actor_id}-{update.sequence:06d}"
        message = Message(to=self.visualization_jid, body=update.to_json())
        message.thread = conversation_id
        message.set_metadata("performative", "inform")
        message.set_metadata("ontology", VISUALIZATION_ONTOLOGY)
        message.set_metadata("language", MESSAGE_LANGUAGE)
        message.set_metadata("conversation-id", conversation_id)
        await behaviour.send(message)
        self.message_trace.record(
            self.agent_label,
            self.visualization_jid.split("@", 1)[0],
            VISUALIZATION_ONTOLOGY,
            "inform",
            conversation_id,
        )
