"""Operazioni SPADE comuni verso l'Environment Agent."""

from __future__ import annotations

import asyncio

from spade.message import Message

from tamagotchi_wild.domain import ActionType, Position
from tamagotchi_wild.messaging import (
    ActionRequest,
    ActionResponse,
    ENVIRONMENT_ONTOLOGY,
    MessageContractError,
    request_metadata,
)


async def environment_action(
    behaviour,
    task_id: str,
    action: ActionType,
    target_id: str,
    destination: Position | None = None,
    quantity: int | None = None,
) -> ActionResponse:
    """Invia un comando correlato e ne valida la risposta JSON."""

    agent = behaviour.agent
    request = ActionRequest(
        task_id=task_id,
        actor_id=agent.agent_label,
        target_id=target_id,
        requested_action=action,
        destination=destination,
        quantity=quantity,
    )
    message = Message(to=agent.environment_jid, body=request.to_json())
    message.thread = task_id
    for key, value in request_metadata(task_id).items():
        message.set_metadata(key, value)
    await behaviour.send(message)
    agent.message_trace.record(
        agent.agent_label,
        agent.environment_jid.split("@", 1)[0],
        ENVIRONMENT_ONTOLOGY,
        "request",
        task_id,
    )

    response = await behaviour.receive(timeout=agent.timeout_seconds)
    if response is None:
        return ActionResponse(
            task_id,
            False,
            f"timeout waiting for {action.value}",
            None,
        )
    try:
        if response.get_metadata("conversation-id") != task_id:
            raise MessageContractError("conversation-id does not match task_id")
        parsed = ActionResponse.from_json(response.body)
        if parsed.task_id != task_id:
            raise MessageContractError("response task_id does not match")
        return parsed
    except MessageContractError as exc:
        return ActionResponse(task_id, False, str(exc), None)


async def claim_task(behaviour, task_id: str, phase: str) -> ActionResponse:
    return await environment_action(
        behaviour,
        task_id,
        ActionType.CLAIM_TASK,
        phase,
    )


async def acquire_area(
    behaviour,
    task_id: str,
    area_id: str,
    destination: Position,
) -> ActionResponse:
    """Attende finche' una stanza ha posto, senza superarne la capienza."""

    deadline = asyncio.get_running_loop().time() + behaviour.agent.timeout_seconds
    while True:
        result = await environment_action(
            behaviour,
            task_id,
            ActionType.ACQUIRE_AREA,
            area_id,
            destination=destination,
        )
        retryable = "is at capacity" in result.reason or "is busy with task" in result.reason
        if result.accepted or not retryable:
            return result
        if asyncio.get_running_loop().time() >= deadline:
            return ActionResponse(
                task_id,
                False,
                f"timeout waiting for access to {area_id}",
                None,
            )
        await asyncio.sleep(0.05)


async def release_area(behaviour, task_id: str, area_id: str) -> ActionResponse:
    return await environment_action(
        behaviour,
        task_id,
        ActionType.RELEASE_AREA,
        area_id,
    )
