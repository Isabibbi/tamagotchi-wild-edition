import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_visualization_agent_receives_live_spade_frames() -> None:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )
    script = """
import json
from queue import Empty, Queue
from tamagotchi_wild.config import SimulationConfig
from tamagotchi_wild.simulation import run_simulation

frames = Queue()
result = run_simulation(
    SimulationConfig(veterinary_agents=1, logistics_agents=1, feeding_agents=1),
    timeout_seconds=60,
    visualization_queue=frames,
)
updates = []
while True:
    try:
        updates.append(frames.get_nowait())
    except Empty:
        break
last = updates[-1].snapshot
print(json.dumps({
    "success": result.success,
    "spade_agent_count": result.spade_agent_count,
    "frame_count": len(updates),
    "first_action": updates[0].event["action"],
    "actions": [item.event["action"] for item in updates],
    "healthy": sum(item["health"] == "healthy" for item in last["animals"]),
    "filled": sum(item["level"] == item["capacity"] for item in last["bowls"]),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )

    assert completed.stdout, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert payload["success"] is True
    assert payload["spade_agent_count"] == 5
    assert payload["frame_count"] > 10
    assert payload["first_action"] == "initial_state"
    assert "fill_bowl" in payload["actions"]
    assert "treat_animal" in payload["actions"]
    assert "return_animal_to_cage" in payload["actions"]
    assert payload["healthy"] == 1
    assert payload["filled"] == 1
