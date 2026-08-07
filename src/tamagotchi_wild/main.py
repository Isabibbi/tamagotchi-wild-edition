"""Comando principale per eseguire gli scenari CRAS disponibili."""

from __future__ import annotations

import argparse

from tamagotchi_wild.feeding_scenario import (
    print_result as print_feeding_result,
    run_feeding_scenario,
)
from tamagotchi_wild.medical_scenario import (
    print_result as print_medical_result,
    run_medical_scenario,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("medical", "feeding"),
        default="medical",
    )
    parser.add_argument("--food", type=int, default=2)
    parser.add_argument("--medicine", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.food < 0 or args.medicine < 0:
        raise SystemExit("resource quantities must not be negative")
    if args.scenario == "feeding":
        result = run_feeding_scenario(args.food, args.timeout)
        print_feeding_result(result, args.as_json)
    else:
        result = run_medical_scenario(args.medicine, args.timeout)
        print_medical_result(result, args.as_json)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
