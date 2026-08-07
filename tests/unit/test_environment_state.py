import pytest

from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    ActionCommand,
    ActionType,
    AgentRole,
    AgentState,
    Animal,
    AreaType,
    HealthStatus,
    Position,
)
from tamagotchi_wild.environment import DuplicateEntityError


def test_default_grid_is_partitioned_into_four_areas() -> None:
    world = create_default_environment()
    snapshot = world.snapshot()

    assert {area.kind for area in snapshot.areas} == set(AreaType)
    assert sum(len(area.cells) for area in snapshot.areas) == 12 * 8


def test_valid_move_changes_state_and_records_event() -> None:
    world = create_default_environment()
    world.register_agent(
        AgentState("logistics-001", AgentRole.LOGISTICS, Position(2, 4))
    )

    result = world.apply(
        ActionCommand(
            actor_id="logistics-001",
            action=ActionType.MOVE_AGENT,
            target_id="logistics-001",
            destination=Position(8, 4),
        )
    )

    assert result.accepted is True
    assert result.event_sequence == 1
    assert world.snapshot().agents[0].position == Position(8, 4)
    assert world.events[0].origin == Position(2, 4)


def test_invalid_move_is_rejected_without_changing_state() -> None:
    world = create_default_environment()
    world.register_agent(
        AgentState("feeding-001", AgentRole.FEEDING, Position(1, 1))
    )

    result = world.apply(
        ActionCommand(
            actor_id="feeding-001",
            action=ActionType.MOVE_AGENT,
            target_id="feeding-001",
            destination=Position(-1, 1),
        )
    )

    assert result.accepted is False
    assert "outside the grid" in result.reason
    assert world.snapshot().agents[0].position == Position(1, 1)
    assert world.events == ()


def test_entity_identifiers_are_unique_across_categories() -> None:
    world = create_default_environment()
    world.register_agent(AgentState("entity-001", AgentRole.FEEDING, Position(1, 1)))

    with pytest.raises(DuplicateEntityError, match="duplicate entity id"):
        world.register_animal(Animal("entity-001", "fox", Position(2, 4)))


def test_health_update_is_an_explicit_environment_action() -> None:
    world = create_default_environment()
    world.register_animal(Animal("animal-001", "fox", Position(2, 4)))

    result = world.apply(
        ActionCommand(
            actor_id="veterinary-001",
            action=ActionType.UPDATE_ANIMAL_HEALTH,
            target_id="animal-001",
            health=HealthStatus.SICK,
        )
    )

    assert result.accepted is True
    assert world.snapshot().animals[0].health is HealthStatus.SICK
