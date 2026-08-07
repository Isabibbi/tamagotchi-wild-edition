import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_seven_agents_complete_feeding_and_medical_workflows_together() -> None:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tamagotchi_wild",
            "--json",
            "--timeout",
            "35",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=75,
        check=False,
    )

    assert completed.stdout, completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["success"] is True
    assert result["operator_count"] == 7
    assert result["spade_agent_count"] == 8
    assert result["feeding_status"] == "completed"
    assert result["medical_status"] == "completed"
    assert result["animal_health"] == "healthy"
    assert result["bowl_level"] == 1
    assert result["food_remaining"] == 1
    assert result["medicine_remaining"] == 0
    assert result["max_room_occupancy"] <= 2
    assert result["active_room_occupancy_at_end"] == 0
    assert len(result["task_claims"]) == 5
    assert result["conversation_ids"] == ["feeding_001", "medical_001"]
