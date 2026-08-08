import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_seven_agents_complete_five_animal_workflows_together() -> None:
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
            "--animals",
            "5",
            "--timeout",
            "90",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
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
    assert result["animal_count"] == 5
    assert result["cage_count"] == 5
    assert result["bowl_count"] == 5
    assert result["feeding_task_count"] == 5
    assert result["medical_task_count"] == 5
    assert result["completed_feeding_tasks"] == 5
    assert result["completed_medical_tasks"] == 5
    assert result["healthy_animals"] == 5
    assert result["filled_bowls"] == 5
    assert result["food_remaining"] == 0
    assert result["medicine_remaining"] == 0
    assert len(set(result["animal_conditions"])) == 5
    assert result["max_room_occupancy"] <= 2
    assert result["active_room_occupancy_at_end"] == 0
    assert len(result["task_claims"]) == 25
    assert len(result["conversation_ids"]) == 10
    assert any("feeding_execution:feeding_02" in claim for claim in result["task_claims"])
    assert any("medical_coordination:veterinary_02" in claim for claim in result["task_claims"])
    assert any("transport_outbound:logistics_03" in claim for claim in result["task_claims"])
