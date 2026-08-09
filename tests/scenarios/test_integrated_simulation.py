import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_seven_agents_complete_ten_animal_workflows_with_safe_transport() -> None:
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
            "10",
            "--timeout",
            "120",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=150,
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
    assert result["animal_count"] == 10
    assert result["cage_count"] == 10
    assert result["bowl_count"] == 10
    assert result["feeding_task_count"] == 10
    assert result["medical_task_count"] == 10
    assert result["completed_feeding_tasks"] == 10
    assert result["completed_medical_tasks"] == 10
    assert result["healthy_animals"] == 10
    assert result["filled_bowls"] == 10
    assert result["food_remaining"] == 0
    assert result["medicine_remaining"] == 0
    assert len(set(result["animal_conditions"])) == 10
    assert result["max_room_occupancy"] <= 2
    assert result["max_treatment_patients"] <= 3
    assert result["treatment_patient_capacity"] == 3
    assert result["max_carried_animals_per_agent"] == 1
    assert result["active_room_occupancy_at_end"] == 0
    assert len(result["task_claims"]) == 50
    assert len(result["conversation_ids"]) == 20
    assert sum("event=patient_ready" in line for line in result["logs"]) == 10
    assert sum("event=treatment_completed" in line for line in result["logs"]) == 10
    assert any("event=waiting_for_treatment_slot" in line for line in result["logs"])
    assert any("feeding_execution:feeding_02" in claim for claim in result["task_claims"])
    assert any("medical_coordination:veterinary_02" in claim for claim in result["task_claims"])
    assert any("transport_outbound:logistics_03" in claim for claim in result["task_claims"])
