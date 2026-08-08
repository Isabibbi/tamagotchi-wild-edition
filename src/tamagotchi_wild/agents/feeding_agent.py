"""Feeding Agent: accetta un task BDI e modifica il mondo tramite SPADE."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Mapping

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
    FEEDING_ONTOLOGY,
    FeedingStatus,
    FeedingTaskRequest,
    MESSAGE_LANGUAGE,
    MessageContractError,
    workflow_metadata,
)
from tamagotchi_wild.observability import ActivityLog, MessageTrace


DEFAULT_ASL = Path(__file__).parents[1] / "bdi" / "feeding.asl"


class FeedingAgent(ProjectBDIAgent):
    class TaskReceiver(CyclicBehaviour):
        async def run(self) -> None:
            message = await self.receive(timeout=1)
            if message is None:
                return
            try:
                request = FeedingTaskRequest.from_json(message.body)
                self.agent._validate_conversation(message, request.task_id)
            except MessageContractError:
                return
            if request.task_id in self.agent.seen_tasks:
                return

            self.agent.seen_tasks.add(request.task_id)
            self.agent.task_requesters[request.task_id] = str(message.sender)
            template = Template()
            template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", request.task_id)
            self.agent.add_behaviour(
                self.agent.ClaimFeedingTask(request),
                template,
            )

    class ClaimFeedingTask(OneShotBehaviour):
        def __init__(self, request: FeedingTaskRequest) -> None:
            super().__init__()
            self.request = request

        async def run(self) -> None:
            result = await claim_task(
                self,
                self.request.task_id,
                "feeding_execution",
            )
            if result.accepted:
                self.agent.bdi.set_belief(
                    "feeding_task",
                    self.request.task_id,
                    self.request.cage_id,
                    self.request.bowl_id,
                )
                return

            requester = self.agent.task_requesters[self.request.task_id]
            body = FeedingStatus(
                self.request.task_id,
                "refused",
                result.reason,
            ).to_json()
            message = _message(
                requester,
                body,
                workflow_metadata(
                    FEEDING_ONTOLOGY,
                    "refuse",
                    self.request.task_id,
                ),
                self.request.task_id,
            )
            await self.send(message)
            self.agent._trace_message(
                requester,
                FEEDING_ONTOLOGY,
                "refuse",
                self.request.task_id,
            )

    class ExecuteFeeding(CyclicBehaviour):
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
            requester = self.agent.task_requesters[self.task_id]
            await self._send_status(requester, "agree", "accepted")
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                "task_accepted",
            )

            take_result = await self._perform_in_area(
                self.agent.food_area_id,
                self.agent.food_position,
                ActionType.TAKE_FOOD,
                self.agent.food_stock_id,
                1,
            )
            if not take_result.accepted:
                await environment_action(
                    self,
                    self.task_id,
                    ActionType.FAIL_TASK,
                    self.task_id,
                )
                await self._fail(requester, take_result.reason)
                self.kill()
                return

            fill_result = await self._perform_in_area(
                self.agent.cage_area_id,
                self.agent.bowl_positions.get(
                    self.bowl_id,
                    self.agent.bowl_position,
                ),
                ActionType.FILL_BOWL,
                self.bowl_id,
                1,
            )
            if not fill_result.accepted:
                await self._fail(requester, fill_result.reason)
                self.kill()
                return

            await self._send_status(requester, "inform", "completed")
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                "task_completed",
            )
            self.agent.bdi.set_belief("feeding_succeeded", self.task_id)
            self.kill()

        async def _perform_in_area(
            self,
            area_id: str,
            destination: Position,
            action: ActionType,
            target_id: str,
            quantity: int | None,
        ) -> ActionResponse:
            access = await acquire_area(
                self,
                self.task_id,
                area_id,
                destination,
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

        async def _send_status(
            self,
            recipient: str,
            performative: str,
            status: str,
            reason: str = "",
        ) -> None:
            body = FeedingStatus(self.task_id, status, reason).to_json()
            message = _message(
                recipient,
                body,
                workflow_metadata(FEEDING_ONTOLOGY, performative, self.task_id),
                self.task_id,
            )
            await self.send(message)
            self.agent._trace_message(
                recipient,
                FEEDING_ONTOLOGY,
                performative,
                self.task_id,
            )

        async def _fail(self, requester: str, reason: str) -> None:
            await self._send_status(requester, "failure", "failed", reason)
            self.agent.failure_reasons[self.task_id] = reason
            self.agent.activity_log.record(
                self.task_id,
                self.agent.agent_label,
                "task_failed",
                reason=reason.replace(" ", "_"),
            )
            self.agent.bdi.set_belief("feeding_failed", self.task_id)

    def __init__(
        self,
        jid: str,
        password: str,
        environment_jid: str,
        food_stock_id: str,
        activity_log: ActivityLog,
        message_trace: MessageTrace,
        timeout_seconds: float = 10.0,
        asl_file: Path = DEFAULT_ASL,
        food_position: Position = Position(1, 1),
        bowl_position: Position = Position(2, 6),
        food_area_id: str = "food-storage",
        cage_area_id: str = "cage-area",
        bowl_positions: Mapping[str, Position] | None = None,
    ) -> None:
        self.environment_jid = environment_jid
        self.food_stock_id = food_stock_id
        self.activity_log = activity_log
        self.message_trace = message_trace
        self.timeout_seconds = timeout_seconds
        self.food_position = food_position
        self.bowl_position = bowl_position
        self.bowl_positions = dict(bowl_positions or {})
        self.food_area_id = food_area_id
        self.cage_area_id = cage_area_id
        self.agent_label = jid.split("@", 1)[0]
        self.seen_tasks: set[str] = set()
        self.task_requesters: dict[str, str] = {}
        self.failure_reasons: dict[str, str] = {}
        self.bdi_outcomes: dict[str, str] = {}
        self.bdi_outcome_ready = asyncio.Event()
        super().__init__(jid, password, str(asl_file))

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "request")
        template.set_metadata("ontology", FEEDING_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.TaskReceiver(), template)

    def add_role_actions(self, actions) -> None:
        @actions.add(".execute_feeding", 3)
        def execute_feeding(agent, term, intention):
            values = [
                term_text(asp.grounded(argument, intention.scope))
                for argument in term.args
            ]
            task_id, cage_id, bowl_id = values
            template = Template()
            template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
            template.set_metadata("language", MESSAGE_LANGUAGE)
            template.set_metadata("conversation-id", task_id)
            self.add_behaviour(
                self.ExecuteFeeding(task_id, cage_id, bowl_id),
                template,
            )
            yield

        @actions.add(".record_feeding_outcome", 2)
        def record_feeding_outcome(agent, term, intention):
            task_id = term_text(asp.grounded(term.args[0], intention.scope))
            outcome = term_text(asp.grounded(term.args[1], intention.scope))
            self.bdi_outcomes[task_id] = outcome
            self.bdi_outcome_ready.set()
            yield

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
        conversation_id = message.get_metadata("conversation-id")
        if conversation_id != task_id:
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
