"""Phase 0: local SPADE-BDI compatibility and communication spike."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

import spade
from spade.behaviour import OneShotBehaviour
from spade.message import Message
from spade.template import Template
from spade_bdi.bdi import BDIAgent

ONTOLOGY = "cras.spike"
LANGUAGE = "json"
PASSWORD = "local-spike-password"
REQUESTER_JID = "requester@localhost"
RESPONDER_JID = "responder@localhost"
BDI_DIR = Path(__file__).with_name("bdi")


@dataclass(frozen=True)
class SpikeResult:
    """Observable outcome of the technical spike."""

    success: bool
    conversation_id: str
    requester_bdi_ready: bool
    responder_bdi_ready: bool
    response_status: str | None
    error: str | None = None


class SpikeBDIAgent(BDIAgent):
    """BDI agent exposing a signal when its AgentSpeak boot plan runs."""

    def __init__(self, jid: str, asl_file: Path) -> None:
        self.bdi_ready = asyncio.Event()
        super().__init__(jid, PASSWORD, str(asl_file))

    def add_custom_actions(self, actions) -> None:
        @actions.add(".mark_bdi_ready", 0)
        def mark_bdi_ready(agent, term, intention):
            self.bdi_ready.set()
            yield


class ResponderAgent(SpikeBDIAgent):
    """Receives one correlated request and returns an acknowledgement."""

    class ReplyBehaviour(OneShotBehaviour):
        async def run(self) -> None:
            message = await self.receive(timeout=self.agent.timeout_seconds)
            if message is None:
                self.agent.exchange_error = "Responder timed out waiting for request."
                self.agent.exchange_done.set()
                return

            conversation_id = message.get_metadata("conversation-id") or ""
            try:
                if not conversation_id:
                    raise ValueError("missing conversation-id")
                payload = json.loads(message.body)
                if payload.get("task_id") != conversation_id:
                    raise ValueError("task_id does not match conversation-id")
                if payload.get("action") != "compatibility_ping":
                    raise ValueError("unexpected spike action")

                response_payload = {
                    "schema_version": 1,
                    "task_id": conversation_id,
                    "status": "acknowledged",
                }
                performative = "inform"
            except (json.JSONDecodeError, ValueError) as exc:
                response_payload = {
                    "schema_version": 1,
                    "task_id": conversation_id,
                    "status": "rejected",
                    "reason": str(exc),
                }
                performative = "failure"

            response = Message(to=str(message.sender))
            response.thread = conversation_id
            response.set_metadata("performative", performative)
            response.set_metadata("ontology", ONTOLOGY)
            response.set_metadata("language", LANGUAGE)
            response.set_metadata("conversation-id", conversation_id)
            response.body = json.dumps(response_payload)
            await self.send(response)

            self.agent.received_conversation_id = conversation_id
            self.agent.exchange_done.set()

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.exchange_done = asyncio.Event()
        self.exchange_error: str | None = None
        self.received_conversation_id: str | None = None
        super().__init__(RESPONDER_JID, BDI_DIR / "responder.asl")

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "request")
        template.set_metadata("ontology", ONTOLOGY)
        self.add_behaviour(self.ReplyBehaviour(), template)


class RequesterAgent(SpikeBDIAgent):
    """Sends one request after both AgentSpeak boot plans are ready."""

    class RequestBehaviour(OneShotBehaviour):
        async def run(self) -> None:
            await self.agent.exchange_allowed.wait()

            conversation_id = self.agent.conversation_id
            request = Message(to=RESPONDER_JID)
            request.thread = conversation_id
            request.set_metadata("performative", "request")
            request.set_metadata("ontology", ONTOLOGY)
            request.set_metadata("language", LANGUAGE)
            request.set_metadata("conversation-id", conversation_id)
            request.body = json.dumps(
                {
                    "schema_version": 1,
                    "task_id": conversation_id,
                    "action": "compatibility_ping",
                }
            )
            await self.send(request)

            response = await self.receive(timeout=self.agent.timeout_seconds)
            if response is None:
                self.agent.exchange_error = "Requester timed out waiting for response."
                self.agent.exchange_done.set()
                return

            try:
                payload = json.loads(response.body)
                if response.get_metadata("conversation-id") != conversation_id:
                    raise ValueError("response conversation-id does not match request")
                if payload.get("task_id") != conversation_id:
                    raise ValueError("response task_id does not match request")
                if response.get_metadata("performative") != "inform":
                    raise ValueError("response performative is not inform")
                self.agent.response_status = payload.get("status")
            except (json.JSONDecodeError, ValueError) as exc:
                self.agent.exchange_error = str(exc)
            finally:
                self.agent.exchange_done.set()

    def __init__(self, conversation_id: str, timeout_seconds: float) -> None:
        self.conversation_id = conversation_id
        self.timeout_seconds = timeout_seconds
        self.exchange_allowed = asyncio.Event()
        self.exchange_done = asyncio.Event()
        self.exchange_error: str | None = None
        self.response_status: str | None = None
        super().__init__(REQUESTER_JID, BDI_DIR / "requester.asl")

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("performative", "inform")
        template.set_metadata("ontology", ONTOLOGY)
        self.add_behaviour(self.RequestBehaviour(), template)


async def execute_spike(timeout_seconds: float = 10.0) -> SpikeResult:
    """Run the two agents against SPADE's embedded XMPP server."""

    conversation_id = f"spike-{uuid4().hex[:12]}"
    responder = ResponderAgent(timeout_seconds)
    requester = RequesterAgent(conversation_id, timeout_seconds)

    try:
        await responder.start(auto_register=True)
        await requester.start(auto_register=True)

        await asyncio.wait_for(
            asyncio.gather(
                requester.bdi_ready.wait(),
                responder.bdi_ready.wait(),
            ),
            timeout=timeout_seconds,
        )

        requester.exchange_allowed.set()
        await asyncio.wait_for(
            asyncio.gather(
                requester.exchange_done.wait(),
                responder.exchange_done.wait(),
            ),
            timeout=timeout_seconds,
        )

        error = requester.exchange_error or responder.exchange_error
        success = (
            error is None
            and requester.response_status == "acknowledged"
            and responder.received_conversation_id == conversation_id
        )
        return SpikeResult(
            success=success,
            conversation_id=conversation_id,
            requester_bdi_ready=requester.bdi_ready.is_set(),
            responder_bdi_ready=responder.bdi_ready.is_set(),
            response_status=requester.response_status,
            error=error,
        )
    except TimeoutError:
        return SpikeResult(
            success=False,
            conversation_id=conversation_id,
            requester_bdi_ready=requester.bdi_ready.is_set(),
            responder_bdi_ready=responder.bdi_ready.is_set(),
            response_status=requester.response_status,
            error=f"Spike timed out after {timeout_seconds:g} seconds.",
        )
    finally:
        await requester.stop()
        await responder.stop()


def run_spike(timeout_seconds: float = 10.0) -> SpikeResult:
    """Run the async scenario and return its result after SPADE shuts down."""

    result_holder: dict[str, SpikeResult] = {}

    async def scenario() -> None:
        result_holder["result"] = await execute_spike(timeout_seconds)

    spade.run(scenario(), embedded_xmpp_server=True)
    return result_holder.get(
        "result",
        SpikeResult(
            success=False,
            conversation_id="not-started",
            requester_bdi_ready=False,
            responder_bdi_ready=False,
            response_status=None,
            error="SPADE stopped before producing a result.",
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_spike(timeout_seconds=args.timeout)

    if args.as_json:
        print(json.dumps(asdict(result), sort_keys=True))
    elif result.success:
        print("PHASE 0 OK")
        print(f"conversation_id={result.conversation_id}")
        print("BDI ready: requester=yes responder=yes")
        print(f"response_status={result.response_status}")
    else:
        print("PHASE 0 FAILED")
        print(f"error={result.error}")

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
