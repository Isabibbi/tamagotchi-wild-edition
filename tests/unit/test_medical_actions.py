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


def acquire(world, actor_id: str, area_id: str, position: Position) -> None:
    result = world.apply(
        command(
            actor_id,
            ActionType.ACQUIRE_AREA,
            target_id=area_id,
            destination=position,
        )
    )
    assert result.accepted


def release(world, actor_id: str, area_id: str) -> None:
    result = world.apply(
        command(actor_id, ActionType.RELEASE_AREA, target_id=area_id)
    )
    assert result.accepted


def apply_in_area(
    world,
    actor_id: str,
    area_id: str,
    position: Position,
    action: ActionType,
    target_id: str = ANIMAL_ID,
    destination: Position | None = None,
    quantity: int | None = None,
):
    acquire(world, actor_id, area_id, position)
    result = world.apply(
        command(actor_id, action, target_id, destination, quantity)
    )
    release(world, actor_id, area_id)
    return result


def test_complete_medical_lifecycle_returns_healthy_animal_to_cage() -> None:
    world = medical_world()

    assert apply_in_area(
        world, LOGISTICS_ID, "cage-area", CAGE_POSITION, ActionType.PICKUP_SICK_ANIMAL
    ).accepted
    assert apply_in_area(
        world,
        LOGISTICS_ID,
        "treatment-room",
        TREATMENT_POSITION,
        ActionType.DELIVER_TO_TREATMENT,
        destination=TREATMENT_POSITION,
    ).accepted
    assert apply_in_area(
        world,
        VETERINARY_ID,
        "medical-storage",
        Position(6, 1),
        ActionType.TAKE_MEDICINE,
        target_id=MEDICINE_ID,
        quantity=1,
    ).accepted
    assert apply_in_area(
        world,
        VETERINARY_ID,
        "treatment-room",
        TREATMENT_POSITION,
        ActionType.TREAT_ANIMAL,
    ).accepted
    assert apply_in_area(
        world,
        LOGISTICS_ID,
        "treatment-room",
        TREATMENT_POSITION,
        ActionType.PICKUP_TREATED_ANIMAL,
    ).accepted
    assert apply_in_area(
        world,
        LOGISTICS_ID,
        "cage-area",
        CAGE_POSITION,
        ActionType.RETURN_ANIMAL_TO_CAGE,
        destination=CAGE_POSITION,
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
    apply_in_area(
        world, LOGISTICS_ID, "cage-area", CAGE_POSITION, ActionType.PICKUP_SICK_ANIMAL
    )
    apply_in_area(
        world,
        LOGISTICS_ID,
        "treatment-room",
        TREATMENT_POSITION,
        ActionType.DELIVER_TO_TREATMENT,
        destination=TREATMENT_POSITION,
    )
    acquire(world, VETERINARY_ID, "treatment-room", TREATMENT_POSITION)

    result = world.apply(command(VETERINARY_ID, ActionType.TREAT_ANIMAL))

    assert result.accepted is False
    assert result.reason == "medicine has not been taken for task medical_001"
    assert world.snapshot().animals[0].health is HealthStatus.IN_TREATMENT


def test_duplicate_pickup_does_not_repeat_transition() -> None:
    world = medical_world()
    pickup = command(LOGISTICS_ID, ActionType.PICKUP_SICK_ANIMAL)
    acquire(world, LOGISTICS_ID, "cage-area", CAGE_POSITION)

    first = world.apply(pickup)
    duplicate = world.apply(pickup)

    assert first.accepted is True
    assert duplicate.accepted is True
    assert duplicate.reason == "already_applied"
    assert len(
        [
            event
            for event in world.events
            if event.action is ActionType.PICKUP_SICK_ANIMAL
        ]
    ) == 1
    assert world.snapshot().animals[0].health is HealthStatus.IN_OUTBOUND_TRANSPORT


def test_take_medicine_fails_without_stock_and_changes_nothing() -> None:
    world = medical_world(medicine_quantity=0)
    apply_in_area(
        world, LOGISTICS_ID, "cage-area", CAGE_POSITION, ActionType.PICKUP_SICK_ANIMAL
    )
    apply_in_area(
        world,
        LOGISTICS_ID,
        "treatment-room",
        TREATMENT_POSITION,
        ActionType.DELIVER_TO_TREATMENT,
        destination=TREATMENT_POSITION,
    )
    acquire(world, VETERINARY_ID, "medical-storage", Position(6, 1))
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


def test_logistics_cannot_pick_up_a_second_animal_while_carrying_one() -> None:
    world = create_default_environment()
    world.register_agent(
        AgentState(LOGISTICS_ID, AgentRole.LOGISTICS, CAGE_POSITION)
    )
    for index in (1, 2):
        animal_id = f"animal_{index:03d}"
        task_id = f"medical_{index:03d}"
        world.register_animal(
            Animal(animal_id, "fox", Position(index + 1, 4), HealthStatus.SICK)
        )
        world.register_task(Task(task_id, TaskType.TREAT_ANIMAL, animal_id))

    def pickup(task_id: str, animal_id: str):
        assert world.apply(
            ActionCommand(
                LOGISTICS_ID,
                ActionType.ACQUIRE_AREA,
                "cage-area",
                destination=CAGE_POSITION,
                task_id=task_id,
            )
        ).accepted
        result = world.apply(
            ActionCommand(
                LOGISTICS_ID,
                ActionType.PICKUP_SICK_ANIMAL,
                animal_id,
                task_id=task_id,
            )
        )
        assert world.apply(
            ActionCommand(
                LOGISTICS_ID,
                ActionType.RELEASE_AREA,
                "cage-area",
                task_id=task_id,
            )
        ).accepted
        return result

    assert pickup("medical_001", "animal_001").accepted
    refused = pickup("medical_002", "animal_002")

    assert refused.accepted is False
    assert refused.reason == "agent logistics_01 already carries animal animal_001"
    snapshot = world.snapshot()
    assert snapshot.animals[0].carried_by == LOGISTICS_ID
    assert snapshot.animals[1].carried_by is None
    assert snapshot.max_carried_animals_per_agent == 1


def test_fourth_patient_waits_in_cage_until_a_treatment_slot_is_freed() -> None:
    world = create_default_environment()
    world.register_medicine_stock(
        MedicineStock(MEDICINE_ID, Position(6, 1), 4)
    )
    world.register_agent(
        AgentState(VETERINARY_ID, AgentRole.VETERINARY, TREATMENT_POSITION)
    )
    logistics_ids = tuple(f"logistics_{index:02d}" for index in range(1, 5))
    for index, logistics_id in enumerate(logistics_ids, start=1):
        animal_id = f"animal_{index:03d}"
        task_id = f"medical_{index:03d}"
        position = Position(index + 1, 4)
        world.register_agent(
            AgentState(logistics_id, AgentRole.LOGISTICS, position)
        )
        world.register_animal(
            Animal(animal_id, "fox", position, HealthStatus.SICK)
        )
        world.register_task(Task(task_id, TaskType.TREAT_ANIMAL, animal_id))

    def area_action(
        actor_id: str,
        task_id: str,
        area_id: str,
        area_position: Position,
        action: ActionType,
        target_id: str,
        destination: Position | None = None,
        quantity: int | None = None,
    ):
        assert world.apply(
            ActionCommand(
                actor_id,
                ActionType.ACQUIRE_AREA,
                area_id,
                destination=area_position,
                task_id=task_id,
            )
        ).accepted
        result = world.apply(
            ActionCommand(
                actor_id,
                action,
                target_id,
                destination=destination,
                quantity=quantity,
                task_id=task_id,
            )
        )
        assert world.apply(
            ActionCommand(
                actor_id,
                ActionType.RELEASE_AREA,
                area_id,
                task_id=task_id,
            )
        ).accepted
        return result

    for index in range(1, 4):
        task_id = f"medical_{index:03d}"
        animal_id = f"animal_{index:03d}"
        logistics_id = f"logistics_{index:02d}"
        assert area_action(
            logistics_id,
            task_id,
            "cage-area",
            Position(index + 1, 4),
            ActionType.PICKUP_SICK_ANIMAL,
            animal_id,
        ).accepted
        assert area_action(
            logistics_id,
            task_id,
            "treatment-room",
            TREATMENT_POSITION,
            ActionType.DELIVER_TO_TREATMENT,
            animal_id,
            destination=TREATMENT_POSITION,
        ).accepted

    fourth_pickup = area_action(
        "logistics_04",
        "medical_004",
        "cage-area",
        Position(5, 4),
        ActionType.PICKUP_SICK_ANIMAL,
        "animal_004",
    )
    assert fourth_pickup.accepted is False
    assert fourth_pickup.reason == "treatment room patient capacity is full"
    assert world.snapshot().animals[3].health is HealthStatus.SICK

    assert area_action(
        VETERINARY_ID,
        "medical_001",
        "medical-storage",
        Position(6, 1),
        ActionType.TAKE_MEDICINE,
        MEDICINE_ID,
        quantity=1,
    ).accepted
    assert area_action(
        VETERINARY_ID,
        "medical_001",
        "treatment-room",
        TREATMENT_POSITION,
        ActionType.TREAT_ANIMAL,
        "animal_001",
    ).accepted
    assert area_action(
        "logistics_01",
        "medical_001",
        "treatment-room",
        TREATMENT_POSITION,
        ActionType.PICKUP_TREATED_ANIMAL,
        "animal_001",
    ).accepted

    assert area_action(
        "logistics_04",
        "medical_004",
        "cage-area",
        Position(5, 4),
        ActionType.PICKUP_SICK_ANIMAL,
        "animal_004",
    ).accepted
    snapshot = world.snapshot()
    assert len(snapshot.treatment_patients) == 2
    assert snapshot.treatment_reserved_count == 3
    assert snapshot.max_treatment_patients == 3
    assert snapshot.max_carried_animals_per_agent == 1
