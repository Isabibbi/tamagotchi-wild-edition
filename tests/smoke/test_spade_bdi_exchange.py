import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_two_bdi_agents_exchange_correlated_message() -> None:
    env = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = source_path + os.pathsep + env.get("PYTHONPATH", "")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tamagotchi_wild.spike",
            "--json",
            "--timeout",
            "15",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["success"] is True
    assert result["requester_bdi_ready"] is True
    assert result["responder_bdi_ready"] is True
    assert result["response_status"] == "acknowledged"
    assert result["conversation_id"].startswith("spike-")
