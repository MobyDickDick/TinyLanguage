import subprocess
from pathlib import Path


REPOSITORY = Path(__file__).parents[2]
SCRIPT = REPOSITORY / "scripts" / "test-logisim-local.sh"


def test_local_logisim_launcher_reports_a_missing_jar(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path / "missing.jar")],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Logisim JAR does not exist" in result.stderr


def test_local_logisim_jar_is_ignored_by_git(tmp_path):
    jar = REPOSITORY / "hardware" / "logisim" / "logisim-evolution-4.1.0-all.jar"
    result = subprocess.run(
        ["git", "check-ignore", str(jar)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
