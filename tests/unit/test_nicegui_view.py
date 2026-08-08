from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.domain import ActionCommand, ActionType, Position
from tamagotchi_wild.main import build_parser
from tamagotchi_wild.simulation import build_environment
from tamagotchi_wild.visualization import (
    render_area_access,
    render_grid_svg,
    render_operator_roster,
    snapshot_metrics,
)


def test_svg_shows_only_agents_with_an_active_room_access() -> None:
    config = SimulationConfig(
        veterinary_agents=1,
        logistics_agents=1,
        feeding_agents=1,
    )
    world = build_environment(config, food=1, medicine=1)
    accepted = world.apply(
        ActionCommand(
            actor_id="feeding_01",
            action=ActionType.ACQUIRE_AREA,
            target_id="food-storage",
            destination=Position(1, 1),
            task_id="feeding_001",
        )
    )

    svg = render_grid_svg(_payload(world))

    assert accepted.accepted is True
    assert "feeding_01" in svg
    assert "logistics_01" not in svg
    assert "veterinary_01" not in svg
    assert "Griglia del centro di recupero" in svg


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

    assert metrics.animal_count == 2
    assert metrics.bowl_count == 2
    assert metrics.medical_task_count == 2
    assert metrics.active_operators == 0
    assert roster.count("staff-chip staff-idle") == 3
    assert "feeding_01" in roster
    assert "0/2" in access


def test_cli_exposes_nicegui_port_and_browser_control() -> None:
    args = build_parser().parse_args(
        ["--gui", "--gui-port", "8090", "--gui-no-browser"]
    )

    assert args.gui is True
    assert args.gui_port == 8090
    assert args.gui_no_browser is True


def _payload(world) -> dict:
    from tamagotchi_wild.messaging import VisualizationUpdate

    return VisualizationUpdate.from_world(world.snapshot(), None).snapshot
