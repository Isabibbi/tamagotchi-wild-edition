from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.domain import ActionType
from tamagotchi_wild.messaging import ActionRequest, VisualizationUpdate
from tamagotchi_wild.simulation import build_environment
from tamagotchi_wild.visualization import timeline_entries


def test_visualization_update_round_trip_contains_complete_world() -> None:
    world = build_environment(
        SimulationConfig(animal_count=2),
        food=2,
        medicine=2,
    )

    original = VisualizationUpdate.from_world(world.snapshot(), None)
    restored = VisualizationUpdate.from_json(original.to_json())

    assert restored.sequence == 0
    assert restored.event["action"] == "initial_state"
    assert restored.snapshot["width"] == 12
    assert restored.snapshot["height"] == 8
    assert len(restored.snapshot["areas"]) == 4
    assert len(restored.snapshot["animals"]) == 2
    assert len(restored.snapshot["cages"]) == 2
    assert len(restored.snapshot["bowls"]) == 2
    assert len(restored.snapshot["tasks"]) == 4


def test_rejected_area_access_becomes_a_readable_wait_event() -> None:
    world = build_environment(SimulationConfig(), food=1, medicine=1)
    request = ActionRequest(
        task_id="medical_001",
        actor_id="logistics_03",
        target_id="treatment-room",
        requested_action=ActionType.ACQUIRE_AREA,
    )
    update = VisualizationUpdate.from_rejected_action(
        world.snapshot(),
        request,
        "area treatment-room is at capacity",
    )

    entries, seen = timeline_entries(update, 0)

    assert seen == 0
    assert update.event["requested_action"] == "acquire_area"
    assert any("logistics_03 attende un posto" in entry for entry in entries)
    assert any("treatment-room" in entry for entry in entries)
