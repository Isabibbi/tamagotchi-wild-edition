from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.domain import ActionCommand, ActionType, Position
from tamagotchi_wild.main import build_parser
from tamagotchi_wild.simulation import build_environment
from tamagotchi_wild.visualization import (
    render_area_access,
    render_floorplan_svg,
    render_operator_roster,
    snapshot_metrics,
)
from tamagotchi_wild.visualization.nicegui_theme import NICEGUI_CSS


def test_floorplan_shows_rooms_cages_and_all_humanoid_operators() -> None:
    config = SimulationConfig(
        veterinary_agents=1,
        logistics_agents=1,
        feeding_agents=1,
    )
    world = build_environment(config, food=1, medicine=1)
    previous = _payload(world)
    accepted = world.apply(
        ActionCommand(
            actor_id="feeding_01",
            action=ActionType.ACQUIRE_AREA,
            target_id="food-storage",
            destination=Position(1, 1),
            task_id="feeding_001",
        )
    )

    svg = render_floorplan_svg(
        _payload(world),
        previous_snapshot=previous,
        transition_seconds=0.25,
    )

    assert accepted.accepted is True
    assert "feeding_01" in svg
    assert "logistics_01" in svg
    assert "veterinary_01" in svg
    assert "Illustrated floorplan of the rescue centre" in svg
    assert "FOOD STORAGE" in svg
    assert "MEDICAL STORAGE" in svg
    assert "CAGE AREA" in svg
    assert "TREATMENT ROOM" in svg
    assert 'class="animal-cage"' in svg
    assert 'class="cage-bar"' in svg
    assert "human-head" in svg
    assert "human-leg-left" in svg
    assert "operator-walking" in svg
    assert "animateTransform" in svg
    assert "Griglia del centro" not in svg
    assert "Waiting operator" not in svg
    assert "Active operator" not in svg


def test_roster_metrics_and_capacity_remain_visible() -> None:
    config = SimulationConfig(
        veterinary_agents=1,
        logistics_agents=1,
        feeding_agents=1,
        animal_count=2,
    )
    world = build_environment(config, food=2, medicine=2)
    payload = _payload(world)

    metrics = snapshot_metrics(payload)
    roster = render_operator_roster(payload)
    access = render_area_access(payload)
    floorplan = render_floorplan_svg(payload)

    assert metrics.animal_count == 2
    assert metrics.bowl_count == 2
    assert metrics.medical_task_count == 2
    assert metrics.active_operators == 0
    assert roster.count("staff-chip staff-idle") == 3
    assert roster.count("staff-person") == 3
    assert "feeding_01" in roster
    assert "0/2" in access
    assert "Patients 0/3" in access or "Pazienti 0/3" in access
    assert "MAX 3 PATIENTS" in floorplan
    assert "P 0/3" in floorplan
    assert floorplan.count('class="animal-cage"') == 2
    assert floorplan.count('class="cage-bowl"') == 2
    assert floorplan.count('data-state="empty"') == 2
    assert "Bowl legend: green full, red empty" in floorplan
    assert "&#x25A6;" in floorplan
    assert '<circle cx="71" cy="359" r="13"/>' not in floorplan
    assert "Waiting operator" not in floorplan
    assert "Active operator" not in floorplan
    assert "Free" in floorplan


def test_operator_status_colors_free_busy_waiting() -> None:
    from tamagotchi_wild.visualization.nicegui_view import _operator_status

    config = SimulationConfig(
        veterinary_agents=1,
        logistics_agents=1,
        feeding_agents=1,
        animal_count=1,
    )
    world = build_environment(config, food=1, medicine=1)
    payload = _payload(world)

    agent_vet = payload["agents"][2]  # veterinary_01
    status_key, label, color = _operator_status(agent_vet, payload)
    assert status_key == "free"
    assert label == "Free"
    assert color == "#16a34a"

    world.apply(
        ActionCommand(
            actor_id="feeding_01",
            action=ActionType.ACQUIRE_AREA,
            target_id="food-storage",
            destination=Position(1, 1),
            task_id="feeding_001",
        )
    )
    busy_payload = _payload(world)
    agent_feeding = next(a for a in busy_payload["agents"] if a["id"] == "feeding_01")
    b_status, b_label, b_color = _operator_status(agent_feeding, busy_payload)
    assert b_status == "busy"
    assert b_label == "Busy"
    assert b_color == "#dc2626"

    # Claim medical task so vet is assigned/waiting for patient transport
    world.apply(
        ActionCommand(
            actor_id="veterinary_01",
            action=ActionType.CLAIM_TASK,
            target_id="medical_coordination",
            task_id="medical_001",
        )
    )
    waiting_payload = _payload(world)
    agent_vet_waiting = next(a for a in waiting_payload["agents"] if a["id"] == "veterinary_01")
    w_status, w_label, w_color = _operator_status(agent_vet_waiting, waiting_payload)
    assert w_status == "waiting"
    assert w_label == "Waiting"
    assert w_color == "#64748b"


def test_full_bowl_is_drawn_as_a_labelled_bowl_with_food() -> None:
    world = build_environment(SimulationConfig(), food=1, medicine=1)
    payload = _payload(world)
    payload["bowls"][0]["level"] = payload["bowls"][0]["capacity"]

    svg = render_floorplan_svg(payload)

    assert 'class="cage-bowl" data-state="full"' in svg
    assert 'aria-label="Bowl full"' in svg
    assert 'class="bowl-content"' in svg


def test_timeline_wraps_long_events_instead_of_cutting_them() -> None:
    assert ".event-log .timeline-entry" in NICEGUI_CSS
    assert "white-space: normal" in NICEGUI_CSS
    assert "overflow-wrap: anywhere" in NICEGUI_CSS
    assert "overflow-x: hidden" in NICEGUI_CSS
    assert ".event-log .timeline-warning" in NICEGUI_CSS
    assert "border-left: 5px solid #fbbf24" in NICEGUI_CSS


def test_cli_exposes_nicegui_port_and_browser_control() -> None:
    args = build_parser().parse_args(
        ["--gui", "--gui-port", "8090", "--gui-no-browser"]
    )

    assert args.gui is True
    assert args.gui_port == 8090
    assert args.gui_no_browser is True


def test_floorplan_scales_to_forty_distinct_cages() -> None:
    config = SimulationConfig(animal_count=40)
    world = build_environment(config, food=40, medicine=40)

    svg = render_floorplan_svg(_payload(world))

    assert svg.count('class="animal-cage"') == 40
    assert 'data-cage-id="cage_40"' in svg
    assert "grid-cell" not in svg


def _payload(world) -> dict:
    from tamagotchi_wild.messaging import VisualizationUpdate

    return VisualizationUpdate.from_world(world.snapshot(), None).snapshot
