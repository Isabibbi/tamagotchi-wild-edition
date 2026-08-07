"""Contratti di messaggistica indipendenti dal comportamento degli agenti."""

from tamagotchi_wild.messaging.contracts import (
    ActionRequest,
    ActionResponse,
    ENVIRONMENT_ONTOLOGY,
    MESSAGE_LANGUAGE,
    MessageContractError,
    request_metadata,
)
from tamagotchi_wild.messaging.feeding import (
    BowlEmptyPerception,
    FEEDING_ONTOLOGY,
    FeedingStatus,
    FeedingTaskRequest,
    PERCEPTION_ONTOLOGY,
    workflow_metadata,
)
from tamagotchi_wild.messaging.medical import (
    OUTBOUND,
    RETURN,
    SickAnimalPerception,
    TRANSPORT_ONTOLOGY,
    TransportRequest,
    TransportStatus,
)

__all__ = [
    "ActionRequest",
    "ActionResponse",
    "ENVIRONMENT_ONTOLOGY",
    "MESSAGE_LANGUAGE",
    "MessageContractError",
    "request_metadata",
    "BowlEmptyPerception",
    "FEEDING_ONTOLOGY",
    "FeedingStatus",
    "FeedingTaskRequest",
    "PERCEPTION_ONTOLOGY",
    "workflow_metadata",
    "OUTBOUND",
    "RETURN",
    "SickAnimalPerception",
    "TRANSPORT_ONTOLOGY",
    "TransportRequest",
    "TransportStatus",
]
