"""Tests for the pinned real-Logisim TinyCPU smoke-test runner."""

from pathlib import Path
import subprocess

import tiny_cpu_logisim as runner


CI_WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"


def completed(command: list[str], stdout: str = "", stderr: str = ""):
    """Build a successful subprocess result for the small command doubles."""
    return subprocess.CompletedProcess(command, 0, stdout, stderr)


def test_verify_java_accepts_only_pinned_runtime(monkeypatch):
    """The launcher must not silently accept the runner image's default JDK."""
    monkeypatch.setattr(
        runner,
        "_run",
        lambda command: completed(command, stderr='openjdk version "21.0.8" 2025-07-15\n'),
    )
    runner.verify_java("java")

    monkeypatch.setattr(
        runner,
        "_run",
        lambda command: completed(command, stderr='openjdk version "21.0.7" 2025-04-15\n'),
    )
    try:
        runner.verify_java("java")
    except runner.SmokeTestError as exc:
        assert "Java 21.0.8 is required; found 21.0.7" in str(exc)
    else:
        raise AssertionError("an unpinned Java runtime was accepted")


def test_smoke_test_logs_version_before_loading_project(tmp_path, monkeypatch):
    """The real load command selects the maintained integration circuit."""
    jar = tmp_path / "logisim.jar"
    project = tmp_path / "TinyCPU.circ"
    jar.write_bytes(b"jar")
    project.write_text("<project/>", encoding="utf-8")
    commands = []

    def fake_run(command, *, timeout=120):
        commands.append(command)
        output = "Logisim-evolution 4.1.0\n" if "--version" in command else ""
        return completed(command, stdout=output)

    monkeypatch.setattr(runner, "_run", fake_run)
    runner.smoke_test("java", jar, project)

    assert commands[0][-1] == "--version"
    assert commands[1][-3:] == ["-tty", "table", str(project)]
    assert "-circuit" not in commands[1]


def test_obtain_jar_uses_versioned_url_and_atomic_partial(tmp_path, monkeypatch):
    """A failed or partial download must never become the cached simulator."""
    destination = tmp_path / "cache" / "logisim.jar"
    observed = {}

    def fake_retrieve(url, path):
        observed["url"] = url
        Path(path).write_bytes(b"pinned jar")

    monkeypatch.setattr(runner.urllib.request, "urlretrieve", fake_retrieve)
    runner.obtain_jar(destination)

    assert "/v4.1.0/logisim-evolution-4.1.0-all.jar" in observed["url"]
    assert destination.read_bytes() == b"pinned jar"
    assert not destination.with_suffix(".jar.part").exists()


def test_trace_test_runs_dedicated_harness_and_retains_raw_table(tmp_path, monkeypatch):
    """AP 10 must clock the harness rather than reusing the load-only table."""
    project = tmp_path / "TinyCPU.circ"
    project.write_text(
        '<?xml version="1.0"?><project><main name="TinyCPUMain"/>'
        '<circuit name="TinyCPUMain"/><circuit name="AP5TraceHarness"/></project>',
        encoding="utf-8",
    )
    program = tmp_path / "program.tcpu"
    program.write_text("HALT()\n", encoding="utf-8")
    output = tmp_path / "artifacts" / "trace.tsv"
    header = "\t".join(runner.integration_trace_from_table.__globals__["INTEGRATION_TABLE_COLUMNS"])
    row = "\t".join(["0", "0", "0", "0", "0", "0", "1", "0", *(["0"] * 6), "1", "0"])
    commands = []

    def fake_run(command, *, timeout=120):
        commands.append(command)
        generated = Path(command[-1]).read_text(encoding="utf-8")
        assert '<main name="AP5TraceHarness"' in generated
        return completed(command, stdout=f"{header}\n{row}\n")

    monkeypatch.setattr(runner, "_run", fake_run)
    runner.trace_test("java", tmp_path / "logisim.jar", project, program, output)

    assert commands[0][-3:-1] == ["-tty", "table"]
    assert output.read_text(encoding="utf-8") == f"{header}\n{row}\n"


def test_ci_publishes_the_raw_electrical_trace_even_on_failure():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "--trace-output artifacts/ci/tinycpu-ap5-logisim.tsv" in workflow
    assert "name: tinycpu-ap5-logisim-table" in workflow
    assert "if: always()" in workflow


def test_ci_uses_available_temurin_build_and_current_setup_action():
    """Keep the pinned JDK resolvable and avoid setup-java's Node 20 runtime."""
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "uses: actions/setup-java@v5" in workflow
    assert "java-version: '21.0.8+9.0.LTS'" in workflow
    assert "actions/setup-java@v4" not in workflow
