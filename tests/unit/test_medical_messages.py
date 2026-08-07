import pytest

from tamagotchi_wild.messaging import (
    MessageContractError,
    OUTBOUND,
    RETURN,
    SickAnimalPerception,
    TransportRequest,
    TransportStatus,
)


def test_sick_animal_perception_round_trip() -> None:
    original = SickAnimalPerception("medical_001", "animal_001", "cage_01")

    assert SickAnimalPerception.from_json(original.to_json()) == original


@pytest.mark.parametrize("direction", [OUTBOUND, RETURN])
def test_transport_request_round_trip(direction: str) -> None:
    original = TransportRequest(
        "medical_001",
        "animal_001",
        "cage_01",
        direction,
    )

    assert TransportRequest.from_json(original.to_json()) == original


def test_transport_status_rejects_unknown_state() -> None:
    body = TransportStatus("medical_001", "animal_001", "accepted").to_json()
    malformed = body.replace("accepted", "teleported")

    with pytest.raises(MessageContractError, match="invalid transport status"):
        TransportStatus.from_json(malformed)
