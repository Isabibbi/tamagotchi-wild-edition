from tamagotchi_wild.agents.environment_agent import EnvironmentAgent
from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.domain import ActionType
from tamagotchi_wild.messaging import ActionRequest, VisualizationUpdate
from tamagotchi_wild.simulation import build_environment
from tamagotchi_wild.visualization import timeline_entries
from tamagotchi_wild.visualization.timeline import (
    describe_activity,
    describe_environment_event,
)


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
    assert restored.snapshot["treatment"] == {
        "patients": [],
        "patient_count": 0,
        "patient_capacity": 3,
        "reserved_count": 0,
        "max_observed": 0,
    }
    assert restored.snapshot["max_carried_animals_per_agent"] == 0


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
    assert any("The treatment room is at full capacity" in entry for entry in entries)
    assert any(
        "Logistics operator 3 tries to enter but must wait" in entry
        for entry in entries
    )


def test_rejected_cage_access_explains_the_attempt_and_the_reason() -> None:
    entry = describe_environment_event(
        {
            "sequence": 12,
            "action": "action_rejected",
            "requested_action": "acquire_area",
            "actor_id": "logistics_02",
            "target_id": "cage-area",
            "task_id": "medical_004",
            "detail": "area cage-area is at capacity",
        }
    )

    assert entry == (
        "#012 · The cage area is at full capacity. Logistics operator 2 "
        "tries to enter but must wait."
    )


def test_other_temporary_blocks_are_explained_clearly() -> None:
    room_full = describe_environment_event(
        {
            "sequence": 20,
            "action": "action_rejected",
            "requested_action": "pickup_sick_animal",
            "actor_id": "logistics_01",
            "target_id": "animal_004",
            "task_id": "medical_004",
            "detail": "treatment room patient capacity is full",
        }
    )
    already_carrying = describe_environment_event(
        {
            "sequence": 21,
            "action": "action_rejected",
            "requested_action": "pickup_sick_animal",
            "actor_id": "logistics_01",
            "target_id": "animal_005",
            "task_id": "medical_005",
            "detail": "agent logistics_01 already carries animal animal_001",
        }
    )

    assert "tries to pick up animal 4" in room_full
    assert "all 3 slots in the treatment room are taken" in room_full
    assert "tries to pick up" in already_carrying and "animal 5" in already_carrying
    assert "already carrying another animal" in already_carrying


def test_identical_retries_produce_one_warning_until_the_action_succeeds() -> None:
    agent = object.__new__(EnvironmentAgent)
    agent._active_visualization_rejections = set()
    request = ActionRequest(
        task_id="medical_004",
        actor_id="logistics_02",
        target_id="cage-area",
        requested_action=ActionType.ACQUIRE_AREA,
    )

    assert agent._should_publish_visualization_rejection(
        request,
        "area cage-area is at capacity",
    )
    assert not agent._should_publish_visualization_rejection(
        request,
        "area cage-area is at capacity",
    )

    agent._clear_visualization_rejection(request)

    assert agent._should_publish_visualization_rejection(
        request,
        "area cage-area is at capacity",
    )


def test_environment_events_use_simple_italian_names() -> None:
    assert describe_environment_event(
        {
            "sequence": 7,
            "action": "acquire_area",
            "actor_id": "feeding_02",
            "target_id": "food-storage",
            "task_id": "feeding_005",
        }
    ) == "#007 · Feeding staff 2 enters into the food storage."

    assert describe_environment_event(
        {
            "sequence": 8,
            "action": "deliver_to_treatment",
            "actor_id": "logistics_01",
            "target_id": "animal_005",
            "task_id": "medical_005",
        }
    ) == "#008 · Logistics operator 1 brings the animal 5 to the treatment room."

    assert describe_environment_event(
        {
            "sequence": 9,
            "action": "treat_animal",
            "actor_id": "veterinary_01",
            "target_id": "animal_005",
            "task_id": "medical_005",
        }
    ) == "#009 · Vet 1 treats the animal 5."


def test_agent_activities_explain_the_medical_flow_without_technical_words() -> None:
    patient_ready = describe_activity(
        "task=medical_005 agent=logistics_02 event=patient_ready animal=animal_005"
    )
    waiting = describe_activity(
        "task=medical_005 agent=logistics_02 "
        "event=waiting_for_treatment_slot animal=animal_005"
    )
    returned = describe_activity(
        "task=medical_005 agent=logistics_02 event=returned animal=animal_005"
    )

    assert patient_ready == (
        "     ↳ The animal 5 has arrived in the treatment room: "
        "the vet begins treatment."
    )
    assert waiting == (
        "     ↳ Treatment room is full: the animal 5 stays in its cage."
    )
    assert returned == "     ↳ The animal 5 has returned to its cage."
    for entry in (patient_ready, waiting, returned):
        assert "task" not in entry
        assert "outbound" not in entry
        assert "medical_" not in entry


def test_waiting_feeding_task_explains_that_the_operator_is_busy() -> None:
    entry = describe_activity(
        "task=feeding_005 agent=feeding_01 event=feeding_task_waiting"
    )

    assert entry == (
        "     ↳ Feeding staff 1 is already filling another bowl: "
        "the request for bowl 5 is on hold."
    )


def test_task_assignment_is_explained_without_internal_phase_names() -> None:
    entry = describe_environment_event(
        {
            "sequence": 4,
            "action": "claim_task",
            "actor_id": "veterinary_02",
            "target_id": "medical_coordination",
            "task_id": "medical_005",
        }
    )

    assert entry == "#004 · Vet 2 takes care of animal 5."
    assert "medical_coordination" not in entry
    assert "claim" not in entry
