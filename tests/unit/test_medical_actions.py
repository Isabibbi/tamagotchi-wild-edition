from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    ActionCommand,
    ActionType,
    AgentRole,
    AgentState,
    Animal,
    HealthStatus,
    MedicineStock,
    Position,
    Task,
    TaskStatus,
    TaskType,
)


TASK_ID = "medical_001"
ANIMAL_ID = "animal_001"
LOGISTICS_ID = "logistics_01"
VETERINARY_ID = "veterinary_01"
MEDICINE_ID = "medicine_stock_01"
CAGE_POSITION = Position(2, 4)
TREATMENT_POSITION = Position(9, 4)


def medical_world(medicine_quantity: int = 1):
    world = create_default_environment()
    world.register_animal(
        Animal(ANIMAL_ID, "fox", CAGE_POSITION, HealthStatus.SICK)
    )
    world.register_medicine_stock(
        MedicineStock(MEDICINE_ID, Position(6, 1), medicine_quantity)
    )
    world.register_agent(
        AgentState(LOGISTICS_ID, AgentRole.LOGISTICS, CAGE_POSITION)
    )
    world.register_agent(
        AgentState(VETERINARY_ID, AgentRole.VETERINARY, TREATMENT_POSITION)
    )
    world.register_task(Task(TASK_ID, TaskType.TREAT_ANIMAL, ANIMAL_ID))
    return world


def command(
    actor_id: str,
    action: ActionType,
    target_id: str = ANIMAL_ID,
    destination: Position | None = None,
    quantity: int | None = None,
) -> ActionCommand:
    return ActionCommand(
        actor_id=actor_id,
        action=action,
        target_id=target_id,
        task_id=TASK_ID,
        destination=destination,
        quantity=quantity,
    )


def test_complete_medical_lifecycle_returns_healthy_animal_to_cage() -> None:
    world = medical_world()

    assert world.apply(command(LOGISTICS_ID, ActionType.PICKUP_SICK_ANIMAL)).accepted
    assert world.apply(
        command(
            LOGISTICS_ID,
            ActionType.DELIVER_TO_TREATMENT,
            destination=TREATMENT_POSITION,
        )
    ).accepted
    assert world.apply(
        command(
            VETERINARY_ID,
            ActionType.TAKE_MEDICINE,
            target_id=MEDICINE_ID,
            quantity=1,
        )
    ).accepted
    assert world.apply(
        command(
            VETERINARY_ID,
            ActionType.MOVE_AGENT,
            target_id=VETERINARY_ID,
            destination=TREATMENT_POSITION,
        )
    ).accepted
    assert world.apply(command(VETERINARY_ID, ActionType.TREAT_ANIMAL)).accepted
    assert world.apply(
        command(LOGISTICS_ID, ActionType.PICKUP_TREATED_ANIMAL)
    ).accepted
    assert world.apply(
        command(
            LOGISTICS_ID,
            ActionType.RETURN_ANIMAL_TO_CAGE,
            destination=CAGE_POSITION,
        )
    ).accepted

    snapshot = world.snapshot()
    animal = snapshot.animals[0]
    assert animal.health is HealthStatus.HEALTHY
    assert animal.position == CAGE_POSITION
    assert animal.carried_by is None
    assert snapshot.medicine_stocks[0].quantity == 0
    assert snapshot.tasks[0].status is TaskStatus.COMPLETED


def test_treatment_requires_medicine_taken_for_same_task() -> None:
    world = medical_world()
    world.apply(command(LOGISTICS_ID, ActionType.PICKUP_SICK_ANIMAL))
    world.apply(
        command(
            LOGISTICS_ID,
            ActionType.DELIVER_TO_TREATMENT,
            destination=TREATMENT_POSITION,
        )
    )

    result = world.apply(command(VETERINARY_ID, ActionType.TREAT_ANIMAL))

    assert result.accepted is False
    assert result.reason == "medicine has not been taken for task medical_001"
    assert world.snapshot().animals[0].health is HealthStatus.IN_TREATMENT


def test_duplicate_pickup_does_not_repeat_transition() -> None:
    world = medical_world()
    pickup = command(LOGISTICS_ID, ActionType.PICKUP_SICK_ANIMAL)

    first = world.apply(pickup)
    duplicate = world.apply(pickup)

    assert first.accepted is True
    assert duplicate.accepted is True
    assert duplicate.reason == "already_applied"
    assert len(world.events) == 1
    assert world.snapshot().animals[0].health is HealthStatus.IN_OUTBOUND_TRANSPORT


def test_take_medicine_fails_without_stock_and_changes_nothing() -> None:
    world = medical_world(medicine_quantity=0)
    world.apply(command(LOGISTICS_ID, ActionType.PICKUP_SICK_ANIMAL))
    world.apply(
        command(
            LOGISTICS_ID,
            ActionType.DELIVER_TO_TREATMENT,
            destination=TREATMENT_POSITION,
        )
    )
    event_count_before = len(world.events)

    result = world.apply(
        command(
            VETERINARY_ID,
            ActionType.TAKE_MEDICINE,
            target_id=MEDICINE_ID,
            quantity=1,
        )
    )

    assert result.accepted is False
    assert result.reason == "not enough medicine"
    assert world.snapshot().medicine_stocks[0].quantity == 0
    assert len(world.events) == event_count_before
