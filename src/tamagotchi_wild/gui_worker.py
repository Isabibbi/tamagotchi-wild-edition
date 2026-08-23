
from __future__ import annotations

import argparse
from multiprocessing.connection import Client

from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.simulation import run_simulation


class ConnectionFrameSink:
    def __init__(self, connection) -> None:
        self.connection = connection

    def put(self, update) -> None:
        self.connection.send(("frame", update))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--authkey", required=True)
    parser.add_argument("--veterinary-agents", required=True, type=int)
    parser.add_argument("--logistics-agents", required=True, type=int)
    parser.add_argument("--feeding-agents", required=True, type=int)
    parser.add_argument("--animals", required=True, type=int)
    parser.add_argument("--food", type=int)
    parser.add_argument("--medicine", type=int)
    parser.add_argument("--timeout", required=True, type=float)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    connection = Client(
        (args.host, args.port),
        family="AF_INET",
        authkey=bytes.fromhex(args.authkey),
    )
    try:
        config = SimulationConfig(
            veterinary_agents=args.veterinary_agents,
            logistics_agents=args.logistics_agents,
            feeding_agents=args.feeding_agents,
            animal_count=args.animals,
        )
        result = run_simulation(
            config,
            food=args.food,
            medicine=args.medicine,
            timeout_seconds=args.timeout,
            visualization_queue=ConnectionFrameSink(connection),
        )
        connection.send(("result", result))
        return 0 if result.success else 1
    except Exception as exc:
        connection.send(("error", f"{type(exc).__name__}: {exc}"))
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
