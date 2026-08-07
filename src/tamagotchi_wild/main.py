"""Anteprima 01: compone e mostra il modello architetturale iniziale."""

from __future__ import annotations

import argparse
import json

from tamagotchi_wild.config import create_default_environment
from tamagotchi_wild.domain import (
    AgentRole,
    AgentState,
    Animal,
    Bowl,
    HealthStatus,
    Position,
)
from tamagotchi_wild.environment import EnvironmentState
from tamagotchi_wild.visualization import project_grid


def build_demo_environment() -> EnvironmentState:
    world = create_default_environment()
    world.register_animal(
        Animal("animal-001", "fox", Position(2, 5), HealthStatus.HEALTHY)
    )
    world.register_bowl(Bowl("bowl-001", "cage-001", Position(3, 5)))
    world.register_agent(
        AgentState("feeding-001", AgentRole.FEEDING, Position(1, 1))
    )
    world.register_agent(
        AgentState("logistics-001", AgentRole.LOGISTICS, Position(4, 4))
    )
    world.register_agent(
        AgentState("veterinary-001", AgentRole.VETERINARY, Position(8, 1))
    )
    return world


def architecture_summary(world: EnvironmentState) -> dict[str, int | str]:
    snapshot = world.snapshot()
    projection = project_grid(snapshot)
    return {
        "preview": "01_architettura_proposta",
        "grid_width": snapshot.width,
        "grid_height": snapshot.height,
        "areas": len(snapshot.areas),
        "animals": len(snapshot.animals),
        "bowls": len(snapshot.bowls),
        "agents": len(snapshot.agents),
        "projected_cells": len(projection.cells),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = architecture_summary(build_demo_environment())
    if args.as_json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("PREVIEW 01 OK")
        print(f"grid={summary['grid_width']}x{summary['grid_height']}")
        print(f"areas={summary['areas']} agents={summary['agents']}")
        print(f"animals={summary['animals']} bowls={summary['bowls']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
