from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    ActionCommand,
    ActionType,
    AgentRole,
    AgentState,
    Position,
)
from tamagotchi_wild.environment import astar_path


def test_astar_finds_a_shortest_route_around_blocked_cells() -> None:
    path = astar_path(
        Position(0, 1),
        Position(4, 1),
        width=5,
        height=3,
        blocked=(Position(2, 0), Position(2, 1)),
    )

    assert path is not None
    assert len(path) == 6
    assert path[-1] == Position(4, 1)
    assert Position(2, 2) in path


def test_area_acquisition_advances_exactly_one_cell_per_request() -> None:
    world = create_default_environment()
    world.register_agent(
        AgentState("feeding_01", AgentRole.FEEDING, Position(13, 4))
    )
    command = ActionCommand(
        "feeding_01",
        ActionType.ACQUIRE_AREA,
        "food-storage",
        destination=Position(1, 1),
        task_id="feeding_001",
    )

    results = []
    for _ in range(30):
        result = world.apply(command)
        results.append(result)
        if result.reason != "moving":
            break

    assert results[-1].accepted is True
    assert results[-1].reason == "accepted"
    movements = [
        event for event in world.events if event.action is ActionType.MOVE_AGENT
    ]
    assert len(movements) > 1
    assert all(
        abs(event.origin.x - event.destination.x)
        + abs(event.origin.y - event.destination.y)
        == 1
        for event in movements
    )
    assert world.snapshot().agents[0].position == Position(1, 1)
    assert world.snapshot().navigation[0].target == Position(1, 1)
    assert world.snapshot().navigation[0].path == ()


def test_navigation_lock_prevents_two_tasks_steering_the_same_agent() -> None:
    world = create_default_environment()
    world.register_agent(
        AgentState("logistics_01", AgentRole.LOGISTICS, Position(2, 4))
    )
    first = world.apply(
        ActionCommand(
            "logistics_01",
            ActionType.ACQUIRE_AREA,
            "cage-area",
            destination=Position(2, 6),
            task_id="medical_001",
        )
    )
    competing = world.apply(
        ActionCommand(
            "logistics_01",
            ActionType.ACQUIRE_AREA,
            "treatment-room",
            destination=Position(11, 6),
            task_id="medical_002",
        )
    )

    assert first.accepted is True
    assert first.reason == "moving"
    assert competing.accepted is False
    assert competing.reason == "agent logistics_01 is navigating for task medical_001"
