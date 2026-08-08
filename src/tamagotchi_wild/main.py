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
    parser.add_argument("--animals", type=int, default=1)
    parser.add_argument("--food", type=int)
    parser.add_argument("--medicine", type=int)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--gui",
        action="store_true",
        help="apre la griglia live e la cronologia ricevute via SPADE",
    )
    parser.add_argument(
        "--gui-delay",
        type=float,
        default=0.20,
        help="secondi tra due aggiornamenti grafici (default: 0.20)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if (args.food is not None and args.food < 0) or (
        args.medicine is not None and args.medicine < 0
    ):
        raise SystemExit("resource quantities must not be negative")
    if args.timeout <= 0:
        raise SystemExit("timeout must be greater than zero")
    if args.gui_delay < 0:
        raise SystemExit("gui delay must not be negative")
    if args.gui and args.as_json:
        raise SystemExit("--gui and --json cannot be used together")
    try:
        config = SimulationConfig(
            veterinary_agents=args.veterinary_agents,
            logistics_agents=args.logistics_agents,
            feeding_agents=args.feeding_agents,
            animal_count=args.animals,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.gui:
        from tamagotchi_wild.gui import run_graphical_simulation

        result = run_graphical_simulation(
            config,
            food=args.food,
            medicine=args.medicine,
            timeout_seconds=args.timeout,
            step_delay_seconds=args.gui_delay,
        )
        if result is None:
            return 0
    else:
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
