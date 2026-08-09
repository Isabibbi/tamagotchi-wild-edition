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
    assert "Pianta illustrata del centro di recupero" in svg
    assert "MAGAZZINO ALIMENTI" in svg
    assert "MAGAZZINO MEDICO" in svg
    assert "AREA GABBIE" in svg
    assert "SALA TRATTAMENTI" in svg
    assert 'class="animal-cage"' in svg
    assert 'class="cage-bar"' in svg
    assert 'class="human-head"' in svg
    assert 'class="human-leg-left"' in svg
    assert 'class="operator operator-walking"' in svg
    assert "animateTransform" in svg
    assert "Griglia del centro" not in svg


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
    assert "Pazienti 0/3" in access
    assert "MASSIMO 3 PAZIENTI" in floorplan
    assert "P 0/3" in floorplan
    assert floorplan.count('class="animal-cage"') == 2


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
