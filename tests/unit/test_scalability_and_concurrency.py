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


def test_runtime_configuration_allows_fifteen_agents() -> None:
    config = SimulationConfig(
        veterinary_agents=5,
        logistics_agents=5,
        feeding_agents=5,
    )
    assert config.operator_count == 15


def test_runtime_configuration_rejects_more_than_fifteen_agents() -> None:
    with pytest.raises(ValueError, match="at most 15"):
        SimulationConfig(veterinary_agents=5, logistics_agents=6, feeding_agents=5)


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


def test_environment_builds_with_ten_and_fifteen_agents() -> None:
    config_10 = SimulationConfig(
        veterinary_agents=2,
        logistics_agents=3,
        feeding_agents=5,
        animal_count=10,
    )
    agents_10 = build_environment(config_10, food=10, medicine=10).snapshot().agents
    assert len(agents_10) == 10

    config_15 = SimulationConfig(
        veterinary_agents=5,
        logistics_agents=5,
        feeding_agents=5,
        animal_count=10,
    )
    agents_15 = build_environment(config_15, food=10, medicine=10).snapshot().agents
    assert len(agents_15) == 15


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
    world.register_bowl(Bowl("bowl_01", "cage_01", Position(2, 4)))
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
    for index in range(1, 4):
        world.register_agent(
            AgentState(
                f"logistics_{index:02d}",
                AgentRole.LOGISTICS,
                Position(index, 4),
            )
        )

    def access(agent_id: str, action: ActionType):
        return world.apply(
            ActionCommand(
                agent_id,
                action,
                "treatment-room",
                destination=(Position(9, 4) if action is ActionType.ACQUIRE_AREA else None),
                task_id="capacity_test",
            )
        )

    assert access("logistics_01", ActionType.ACQUIRE_AREA).accepted
    assert access("logistics_02", ActionType.ACQUIRE_AREA).accepted
    refused = access("logistics_03", ActionType.ACQUIRE_AREA)

    assert refused.accepted is False
    assert refused.reason == "area treatment-room is at capacity"
    assert access("logistics_01", ActionType.RELEASE_AREA).accepted
    assert access("logistics_03", ActionType.ACQUIRE_AREA).accepted

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
            Position(9, 4),
        )
    )

    assert result.accepted is True
    assert attempts == 3
