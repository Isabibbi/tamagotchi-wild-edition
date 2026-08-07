"""Base comune per gli agenti BDI operativi del progetto."""

from __future__ import annotations

import asyncio

import agentspeak as asp
from spade_bdi.bdi import BDIAgent


def term_text(value: object) -> str:
    if isinstance(value, asp.Literal):
        return value.functor
    return str(value)


class ProjectBDIAgent(BDIAgent):
    def __init__(self, jid: str, password: str, asl_file: str) -> None:
        self.bdi_ready = asyncio.Event()
        super().__init__(jid, password, asl_file)

    def add_custom_actions(self, actions) -> None:
        @actions.add(".mark_bdi_ready", 0)
        def mark_bdi_ready(agent, term, intention):
            self.bdi_ready.set()
            yield

        self.add_role_actions(actions)

    def add_role_actions(self, actions) -> None:
        raise NotImplementedError
