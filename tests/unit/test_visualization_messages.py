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
    assert any("La sala cure è al completo" in entry for entry in entries)
    assert any("Operatore logistico 3 aspetta fuori" in entry for entry in entries)


def test_environment_events_use_simple_italian_names() -> None:
    assert describe_environment_event(
        {
            "sequence": 7,
            "action": "acquire_area",
            "actor_id": "feeding_02",
            "target_id": "food-storage",
            "task_id": "feeding_005",
        }
    ) == "#007 · Addetto alimentazione 2 entra nel magazzino del cibo."

    assert describe_environment_event(
        {
            "sequence": 8,
            "action": "deliver_to_treatment",
            "actor_id": "logistics_01",
            "target_id": "animal_005",
            "task_id": "medical_005",
        }
    ) == "#008 · Operatore logistico 1 porta l'animale 5 nella sala cure."

    assert describe_environment_event(
        {
            "sequence": 9,
            "action": "treat_animal",
            "actor_id": "veterinary_01",
            "target_id": "animal_005",
            "task_id": "medical_005",
        }
    ) == "#009 · Veterinario 1 cura l'animale 5."


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
        "     ↳ L'animale 5 è arrivato nella sala cure: "
        "il veterinario inizia la cura."
    )
    assert waiting == (
        "     ↳ La sala cure è piena: l'animale 5 resta nella sua gabbia."
    )
    assert returned == "     ↳ L'animale 5 è tornato nella sua gabbia."
    for entry in (patient_ready, waiting, returned):
        assert "task" not in entry
        assert "outbound" not in entry
        assert "medical_" not in entry


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

    assert entry == "#004 · Veterinario 2 si occupa dell'animale 5."
    assert "medical_coordination" not in entry
    assert "claim" not in entry
