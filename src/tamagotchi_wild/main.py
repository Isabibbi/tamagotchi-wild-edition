"""Avvia la simulazione CRAS integrata e configura gli agenti a runtime."""

from __future__ import annotations

import argparse

from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.simulation import print_result, run_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--veterinary-agents", type=int, default=2)
    parser.add_argument("--logistics-agents", type=int, default=3)
    parser.add_argument("--feeding-agents", type=int, default=2)
    parser.add_argument("--food", type=int, default=2)
    parser.add_argument("--medicine", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.food < 0 or args.medicine < 0:
        raise SystemExit("resource quantities must not be negative")
    try:
        config = SimulationConfig(
            veterinary_agents=args.veterinary_agents,
            logistics_agents=args.logistics_agents,
            feeding_agents=args.feeding_agents,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    result = run_simulation(
        config,
        food=args.food,
        medicine=args.medicine,
        timeout_seconds=args.timeout,
    )
    print_result(result, args.as_json)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
