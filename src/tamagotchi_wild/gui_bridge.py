from __future__ import annotations

import argparse
from collections import deque
from multiprocessing.connection import Client, Listener
import secrets
import subprocess
import sys
import threading

from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.simulation import run_simulation


class ConnectionFrameSink:
    def __init__(self, connection) -> None:
        self.connection = connection

    def put(self, update) -> None:
        self.connection.send(("frame", update))


class SimulationBridge:

    def __init__(
        self,
        config: SimulationConfig,
        food: int | None,
        medicine: int | None,
        timeout_seconds: float,
    ) -> None:
        self.config = config
        self.food = food
        self.medicine = medicine
        self.timeout_seconds = timeout_seconds
        self.result = None
        self.connected = threading.Event()
        self._frames = []
        self._terminal_result = None
        self._state_lock = threading.Lock()
        self._authkey = secrets.token_bytes(32)
        self._listener = Listener(
            ("127.0.0.1", 0),
            family="AF_INET",
            authkey=self._authkey,
        )
        self._connection = None
        self._process: subprocess.Popen | None = None
        self._receiver_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._stderr_lines: deque[str] = deque(maxlen=40)
        self._received_terminal = False
        self._reported_failure = False
        self._stopping = threading.Event()

    def start(self) -> None:
        host, port = self._listener.address
        self._receiver_thread = threading.Thread(
            target=self._receive,
            daemon=True,
            name="nicegui-spade-receiver",
        )
        self._receiver_thread.start()
        command = [
            sys.executable,
            "-m",
            "tamagotchi_wild.gui_bridge",
            "--host",
            host,
            "--port",
            str(port),
            "--authkey",
            self._authkey.hex(),
            "--veterinary-agents",
            str(self.config.veterinary_agents),
            "--logistics-agents",
            str(self.config.logistics_agents),
            "--feeding-agents",
            str(self.config.feeding_agents),
            "--animals",
            str(self.config.animal_count),
            "--timeout",
            str(self.timeout_seconds),
        ]
        if self.food is not None:
            command.extend(("--food", str(self.food)))
        if self.medicine is not None:
            command.extend(("--medicine", str(self.medicine)))
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._stderr_thread = threading.Thread(
            target=self._capture_stderr,
            daemon=True,
            name="nicegui-spade-stderr",
        )
        self._stderr_thread.start()

    def report_process_failure(self) -> None:
        if (
            self._process is None
            or self._process.poll() is None
            or self._received_terminal
            or self._reported_failure
        ):
            return
        self._reported_failure = True
        reason = self._stderr_lines[-1] if self._stderr_lines else "no diagnostic output"
        error = RuntimeError(
            f"SPADE worker stopped with code {self._process.returncode}: {reason}"
        )
        with self._state_lock:
            self._terminal_result = error
            self.result = error

    def frame_at(self, index: int):
        with self._state_lock:
            return self._frames[index] if index < len(self._frames) else None

    def terminal_result(self):
        with self._state_lock:
            return self._terminal_result

    def stop(self) -> None:
        if self._stopping.is_set():
            return
        self._stopping.set()
        if self._process is not None and self._process.poll() is None:
            if self._received_terminal:
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._terminate_process()
            else:
                self._terminate_process()
        self._listener.close()
        if self._receiver_thread is not None:
            self._receiver_thread.join(timeout=2)
        if self._connection is not None:
            self._connection.close()
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=2)

    def _terminate_process(self) -> None:
        process = self._process
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def _receive(self) -> None:
        try:
            self._connection = self._listener.accept()
            self.connected.set()
            while not self._stopping.is_set():
                kind, payload = self._connection.recv()
                if kind == "frame":
                    with self._state_lock:
                        self._frames.append(payload)
                elif kind == "result":
                    self._received_terminal = True
                    with self._state_lock:
                        self._terminal_result = payload
                        self.result = payload
                elif kind == "error":
                    self._received_terminal = True
                    error = RuntimeError(payload)
                    with self._state_lock:
                        self._terminal_result = error
                        self.result = error
        except (EOFError, OSError):
            return

    def _capture_stderr(self) -> None:
        if self._process is None or self._process.stderr is None:
            return
        for line in self._process.stderr:
            clean_line = line.strip()
            if clean_line:
                self._stderr_lines.append(clean_line)


def _build_worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SPADE GUI Worker")
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


def _worker_main() -> int:
    args = _build_worker_parser().parse_args()
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
    raise SystemExit(_worker_main())
