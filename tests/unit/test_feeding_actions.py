from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    ActionCommand,
    ActionType,
    AgentRole,
    AgentState,
    Bowl,
    FoodStock,
    Position,
    Task,
    TaskStatus,
    TaskType,
)


def feeding_world(food_quantity: int = 2):
    world = create_default_environment()
    world.register_bowl(Bowl("bowl_01", "cage_01", Position(2, 4)))
    world.register_food_stock(
        FoodStock("food_stock_01", Position(1, 1), quantity=food_quantity)
    )
    world.register_agent(
        AgentState("feeding_01", AgentRole.FEEDING, Position(1, 1))
    )
    world.register_task(Task("task_001", TaskType.REFILL_BOWL, "bowl_01"))
    return world


def take_food_command() -> ActionCommand:
    return ActionCommand(
        actor_id="feeding_01",
        action=ActionType.TAKE_FOOD,
        target_id="food_stock_01",
        task_id="task_001",
        quantity=1,
    )


def fill_bowl_command() -> ActionCommand:
    return ActionCommand(
        actor_id="feeding_01",
        action=ActionType.FILL_BOWL,
        target_id="bowl_01",
        task_id="task_001",
        quantity=1,
    )


def acquire(world, area_id: str, position: Position) -> None:
    result = world.apply(
        ActionCommand(
            actor_id="feeding_01",
            action=ActionType.ACQUIRE_AREA,
            target_id=area_id,
            task_id="task_001",
            destination=position,
        )
    )
    assert result.accepted


def release(world, area_id: str) -> None:
    result = world.apply(
        ActionCommand(
            actor_id="feeding_01",
            action=ActionType.RELEASE_AREA,
            target_id=area_id,
            task_id="task_001",
        )
    )
    assert result.accepted


def test_take_food_decrements_stock_and_starts_task() -> None:
    world = feeding_world()
    acquire(world, "food-storage", Position(1, 1))

    result = world.apply(take_food_command())
    snapshot = world.snapshot()

    assert result.accepted is True
    assert snapshot.food_stocks[0].quantity == 1
    assert snapshot.tasks[0].status is TaskStatus.IN_PROGRESS
    assert snapshot.tasks[0].assigned_to == "feeding_01"


def test_fill_bowl_completes_task_after_food_was_taken() -> None:
    world = feeding_world()
    acquire(world, "food-storage", Position(1, 1))
    world.apply(take_food_command())
    release(world, "food-storage")
    acquire(world, "cage-area", Position(2, 4))

    result = world.apply(fill_bowl_command())
    snapshot = world.snapshot()

    assert result.accepted is True
    assert snapshot.bowls[0].level == snapshot.bowls[0].capacity
    assert snapshot.tasks[0].status is TaskStatus.COMPLETED


def test_duplicate_take_food_is_idempotent() -> None:
    world = feeding_world()
    acquire(world, "food-storage", Position(1, 1))

    first = world.apply(take_food_command())
    duplicate = world.apply(take_food_command())

    assert first.accepted is True
    assert duplicate.accepted is True
    assert duplicate.reason == "already_applied"
    assert duplicate.event_sequence == first.event_sequence
    assert world.snapshot().food_stocks[0].quantity == 1
    assert len(
        [event for event in world.events if event.action is ActionType.TAKE_FOOD]
    ) == 1


def test_take_food_fails_cleanly_when_storage_is_empty() -> None:
    world = feeding_world(food_quantity=0)
    acquire(world, "food-storage", Position(1, 1))

    result = world.apply(take_food_command())
    snapshot = world.snapshot()

    assert result.accepted is False
    assert result.reason == "not enough food"
    assert snapshot.food_stocks[0].quantity == 0
    assert snapshot.bowls[0].level == 0
    assert snapshot.tasks[0].status is TaskStatus.PENDING
    assert not any(event.action is ActionType.TAKE_FOOD for event in world.events)


def test_fill_bowl_requires_food_taken_for_the_same_task() -> None:
    world = feeding_world()
    acquire(world, "cage-area", Position(2, 4))

    result = world.apply(fill_bowl_command())

    assert result.accepted is False
    assert result.reason == "food has not been taken for task task_001"
    assert world.snapshot().bowls[0].level == 0
