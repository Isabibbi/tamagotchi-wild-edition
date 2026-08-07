"""Adattatore SPADE per l'ambiente centralizzato."""

from __future__ import annotations

import json

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from tamagotchi_wild.environment import EnvironmentState
from tamagotchi_wild.messaging import (
    ActionRequest,
    ActionResponse,
    ENVIRONMENT_ONTOLOGY,
    MESSAGE_LANGUAGE,
    MessageContractError,
)


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

    def __init__(self, jid: str, password: str, world: EnvironmentState) -> None:
        self.world = world
        super().__init__(jid, password)

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "request")
        template.set_metadata("ontology", ENVIRONMENT_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.RequestBehaviour(), template)
