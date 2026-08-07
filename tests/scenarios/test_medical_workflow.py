import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_medical_scenario(medicine: int) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tamagotchi_wild.medical_scenario",
            "--json",
            "--timeout",
            "25",
            "--medicine",
            str(medicine),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=55,
        check=False,
    )


def parse_result(completed: subprocess.CompletedProcess[str]) -> dict:
    assert completed.stdout, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_spade_bdi_agents_complete_full_medical_lifecycle() -> None:
    completed = run_medical_scenario(medicine=1)

    result = parse_result(completed)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["success"] is True
    assert result["veterinary_bdi_ready"] is True
    assert result["logistics_bdi_ready"] is True
    assert result["animal_health"] == "healthy"
    assert result["animal_position"] == [2, 4]
    assert result["animal_carried_by"] is None
    assert result["medicine_before"] == 1
    assert result["medicine_after"] == 0
    assert result["task_status"] == "completed"
    assert result["message_count"] == 21
    assert result["conversation_ids"] == ["medical_001"]


def test_medical_workflow_rejects_task_without_medicine() -> None:
    completed = run_medical_scenario(medicine=0)

    result = parse_result(completed)
    assert completed.returncode == 1
    assert result["success"] is False
    assert result["scenario_status"] == "failed"
    assert result["error"] == "not enough medicine"
    assert result["animal_health"] == "in_treatment"
    assert result["animal_position"] == [9, 4]
    assert result["medicine_after"] == 0
    assert result["task_status"] == "rejected"
    assert result["conversation_ids"] == ["medical_001"]
