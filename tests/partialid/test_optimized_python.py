from pathlib import Path
import os
import subprocess
import sys


def test_invariant_checks_survive_optimized_python() -> None:
    repository = Path(__file__).parents[2]
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    source_path = str(repository / "src")
    environment["PYTHONPATH"] = (
        source_path if not existing else os.pathsep.join((source_path, existing))
    )
    program = """
from housing_pressure.partialid import InvariantViolation, certify_focal_geometry

try:
    certify_focal_geometry([1.0, 2.0], [[1.0]])
except InvariantViolation:
    raise SystemExit(0)
raise SystemExit(7)
"""

    completed = subprocess.run(
        [sys.executable, "-O", "-c", program],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
