"""Contratti di messaggistica indipendenti dal comportamento degli agenti."""

from tamagotchi_wild.messaging.contracts import (
    ActionRequest,
    ActionResponse,
    ENVIRONMENT_ONTOLOGY,
    MESSAGE_LANGUAGE,
    MessageContractError,
    request_metadata,
)

__all__ = [
    "ActionRequest",
    "ActionResponse",
    "ENVIRONMENT_ONTOLOGY",
    "MESSAGE_LANGUAGE",
    "MessageContractError",
    "request_metadata",
]
