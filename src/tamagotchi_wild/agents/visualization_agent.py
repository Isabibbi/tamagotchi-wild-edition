
from __future__ import annotations

import asyncio
from queue import Queue

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from tamagotchi_wild.messaging import (
    MESSAGE_LANGUAGE,
    VISUALIZATION_ONTOLOGY,
    MessageContractError,
    VisualizationUpdate,
)


class VisualizationAgent(Agent):

    class UpdateReceiver(CyclicBehaviour):
        async def run(self) -> None:
            message = await self.receive(timeout=1)
            if message is None:
                return
            try:
                update = VisualizationUpdate.from_json(message.body)
            except MessageContractError:
                return
            self.agent.frame_queue.put(update)

    def __init__(
        self,
        jid: str,
        password: str,
        frame_queue: Queue,
    ) -> None:
        self.frame_queue = frame_queue
        self.ready = asyncio.Event()
        super().__init__(jid, password)

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "inform")
        template.set_metadata("ontology", VISUALIZATION_ONTOLOGY)
        template.set_metadata("language", MESSAGE_LANGUAGE)
        self.add_behaviour(self.UpdateReceiver(), template)
        self.ready.set()
