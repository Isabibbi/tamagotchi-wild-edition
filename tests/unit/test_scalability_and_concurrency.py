import asyncio

import pytest

from tamagotchi_wild.agents import environment_actions as access_module
from tamagotchi_wild.config import SimulationConfig, create_default_environment
from tamagotchi_wild.domain import (
    ActionCommand,
    ActionType,
    AgentRole,
    AgentState,
    AreaType,
    Bowl,
    Position,
    Task,
    TaskType,
)
from tamagotchi_wild.simulation import build_environment


def test_default_configuration_runs_seven_operational_agents() -> None:
    config = SimulationConfig()

    assert config.operator_count == 7
    assert config.veterinary_agents == 2
    assert config.logistics_agents == 3
    assert config.feeding_agents == 2


def test_runtime_configuration_rejects_more_than_seven_agents() -> None:
    with pytest.raises(ValueError, match="at most 7"):
        SimulationConfig(veterinary_agents=2, logistics_agents=4, feeding_agents=2)


def test_runtime_configuration_builds_the_requested_agent_pool() -> None:
    config = SimulationConfig(
        veterinary_agents=1,
        logistics_agents=2,
        feeding_agents=1,
    )

    agents = build_environment(config, food=2, medicine=1).snapshot().agents

    assert len(agents) == 4
    assert [agent.id for agent in agents] == [
        "feeding_01",
        "logistics_01",
        "logistics_02",
        "veterinary_01",
    ]


def test_five_animals_create_five_complete_and_distinct_cases() -> None:
    config = SimulationConfig(animal_count=5)

    snapshot = build_environment(config, food=5, medicine=5).snapshot()

    assert len(snapshot.animals) == 5
    assert len(snapshot.cages) == 5
    assert len(snapshot.bowls) == 5
    assert len(snapshot.tasks) == 10
    assert len({animal.condition for animal in snapshot.animals}) == 5
    assert len({cage.position for cage in snapshot.cages}) == 5
    assert all(
        next(area for area in snapshot.areas if cage.position in area.cells).kind
        is AreaType.CAGE_AREA
        for cage in snapshot.cages
    )
    assert {
        (cage.id, cage.animal_id, cage.bowl_id)
        for cage in snapshot.cages
    } == {
        (f"cage_{index:02d}", f"animal_{index:03d}", f"bowl_{index:02d}")
        for index in range(1, 6)
    }


def test_runtime_configuration_rejects_more_animals_than_cage_cells() -> None:
    with pytest.raises(ValueError, match="between 1 and 40"):
        SimulationConfig(animal_count=41)


def test_task_phase_is_claimed_by_exactly_one_agent() -> None:
    world = create_default_environment()
    world.register_bowl(Bowl("bowl_01", "cage_01", Position(2, 6)))
    world.register_task(Task("feeding_001", TaskType.REFILL_BOWL, "bowl_01"))
    world.register_agent(
        AgentState("feeding_01", AgentRole.FEEDING, Position(1, 1))
    )
    world.register_agent(
        AgentState("feeding_02", AgentRole.FEEDING, Position(2, 1))
    )

    first = world.apply(
        ActionCommand(
            "feeding_01",
            ActionType.CLAIM_TASK,
            "feeding_execution",
            task_id="feeding_001",
        )
    )
    competing = world.apply(
        ActionCommand(
            "feeding_02",
            ActionType.CLAIM_TASK,
            "feeding_execution",
            task_id="feeding_001",
        )
    )
    retry = world.apply(
        ActionCommand(
            "feeding_01",
            ActionType.CLAIM_TASK,
            "feeding_execution",
            task_id="feeding_001",
        )
    )

    assert first.accepted is True
    assert competing.accepted is False
    assert "feeding_01" in competing.reason
    assert retry.accepted is True
    assert retry.reason == "already_claimed"


def test_third_agent_cannot_enter_a_room_until_a_place_is_released() -> None:
    world = create_default_environment()
    for index, position in enumerate(
        (Position(0, 4), Position(6, 4), Position(8, 4)),
        start=1,
    ):
        world.register_agent(
            AgentState(
                f"logistics_{index:02d}",
                AgentRole.LOGISTICS,
                position,
            )
        )

    def access(agent_id: str, action: ActionType, destination=None):
        return world.apply(
            ActionCommand(
                agent_id,
                action,
                "treatment-room",
                destination=destination,
                task_id="capacity_test",
            )
        )

    def enter(agent_id: str):
        for _ in range(50):
            result = access(
                agent_id,
                ActionType.ACQUIRE_AREA,
                Position(11, 6),
            )
            if result.reason != "moving":
                return result
        raise AssertionError(f"{agent_id} did not finish navigation")

    assert enter("logistics_01").accepted
    assert enter("logistics_02").accepted
    refused = enter("logistics_03")

    assert refused.accepted is False
    assert "path blocked" in refused.reason
    assert access("logistics_01", ActionType.RELEASE_AREA).accepted
    assert world.apply(
        ActionCommand(
            "logistics_01",
            ActionType.MOVE_AGENT,
            "logistics_01",
            destination=Position(10, 6),
            task_id="capacity_test",
        )
    ).accepted
    assert world.apply(
        ActionCommand(
            "logistics_01",
            ActionType.MOVE_AGENT,
            "logistics_01",
            destination=Position(9, 6),
            task_id="capacity_test",
        )
    ).accepted
    assert enter("logistics_03").accepted

    treatment = next(
        item
        for item in world.snapshot().area_access
        if item.area_id == "treatment-room"
    )
    assert len(treatment.occupants) == 2
    assert treatment.max_observed == 2
    assert treatment.capacity == 2


def test_agent_waits_and_retries_when_a_room_is_full(monkeypatch) -> None:
    attempts = 0

    async def fake_environment_action(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return access_module.ActionResponse(
                "capacity_test",
                False,
                "area treatment-room is at capacity",
                None,
            )
        return access_module.ActionResponse(
            "capacity_test",
            True,
            "accepted",
            attempts,
        )

    class FakeAgent:
        timeout_seconds = 1.0

    class FakeBehaviour:
        agent = FakeAgent()

    monkeypatch.setattr(access_module, "environment_action", fake_environment_action)

    result = asyncio.run(
        access_module.acquire_area(
            FakeBehaviour(),
            "capacity_test",
            "treatment-room",
            Position(11, 6),
        )
    )

    assert result.accepted is True
    assert attempts == 3
