from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import Animal, Position
from tamagotchi_wild.visualization import project_grid


def test_projection_contains_entities_without_exposing_world_mutation() -> None:
    world = create_default_environment()
    world.register_animal(Animal("animal-001", "fox", Position(2, 4)))

    projection = project_grid(world.snapshot())
    occupied_cell = next(cell for cell in projection.cells if cell.position == Position(2, 4))

    assert len(projection.cells) == 96
    assert occupied_cell.animal_ids == ("animal-001",)
