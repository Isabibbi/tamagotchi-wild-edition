import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_scenario(food: int) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tamagotchi_wild.feeding_scenario",
            "--json",
            "--food",
            str(food),
            "--timeout",
            "20",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )


def result_from(completed: subprocess.CompletedProcess[str]) -> dict:
    assert completed.stdout, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_spade_bdi_agents_complete_feeding_workflow() -> None:
    completed = run_scenario(food=2)
    result = result_from(completed)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["success"] is True
    assert result["feeding_bdi_ready"] is True
    assert result["logistics_bdi_ready"] is True
    assert result["feeding_bdi_outcome"] == "completed"
    assert result["food_before"] == 2
    assert result["food_after"] == 1
    assert result["bowl_level"] == result["bowl_capacity"] == 1
    assert result["task_status"] == "completed"
    assert result["message_count"] == 8
    assert result["conversation_ids"] == ["task_001"]


def test_spade_bdi_agents_report_explicit_failure_without_food() -> None:
    completed = run_scenario(food=0)
    result = result_from(completed)

    assert completed.returncode == 1
    assert result["success"] is False
    assert result["scenario_status"] == "failed"
    assert result["feeding_bdi_outcome"] == "failed"
    assert result["error"] == "not enough food"
    assert result["food_after"] == 0
    assert result["bowl_level"] == 0
    assert result["task_status"] == "rejected"
    assert result["conversation_ids"] == ["task_001"]
