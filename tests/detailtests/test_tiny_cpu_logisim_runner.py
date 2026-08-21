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


def _tty_row(**overrides):
    values = {label: "0" for label, _width in runner.TTY_OUTPUTS}
    values.update(
        {
            "PRINT_VALUE": "0000000000000000",
            "PRINT_ADDRESS_VALUE": "0000000000000000",
        }
    )
    values.update(overrides)
    tokens = []
    for label, width in runner.TTY_OUTPUTS:
        value = values[label]
        tokens.extend(
            [value[index : index + 4] for index in range(0, 16, 4)]
            if width == 16
            else [value]
        )
    return " ".join(tokens)


def test_trace_test_clocks_temporary_main_and_retains_raw_table(tmp_path, monkeypatch):
    """AP 10 must drive TinyCPUMain without an unreliable nested symbol."""
    project = tmp_path / "TinyCPU.circ"
    project.write_text(
        '<?xml version="1.0"?><project><main name="TinyCPUMain"/>'
        '<circuit name="TinyCPUMain">'
        '<comp name="Pin" loc="(0,0)"><a name="label" val="CLK"/></comp>'
        '<comp name="Pin" loc="(0,20)"><a name="label" val="RESET"/></comp>'
        '</circuit><circuit name="FetchDecode"><comp name="ROM">'
        '<a name="contents">addr/data: 12 22\n2c0000\n</a>'
        "</comp></circuit></project>",
        encoding="utf-8",
    )
    program = tmp_path / "program.tcpu"
    program.write_text("HALT()\n", encoding="utf-8")
    output = tmp_path / "artifacts" / "trace.tsv"
    raw_table = _tty_row(HALT_ENABLE="1", HALTED="1", halt="1") + "\n"
    commands = []

    def fake_run(command, *, timeout=120, stdout_path=None):
        commands.append(command)
        generated = Path(command[-1]).read_text(encoding="utf-8")
        assert '<main name="TinyCPUMain"' in generated
        assert 'name="Clock"' in generated
        assert 'name="PowerOnReset"' in generated
        assert 'name="Constant"' not in generated
        assert 'val="TRACE_CLK"' in generated
        assert 'val="halt"' in generated
        if stdout_path is not None:
            stdout_path.write_text(raw_table, encoding="utf-8")
        return completed(command, stdout=raw_table)

    monkeypatch.setattr(runner, "_run", fake_run)
    runner.trace_test("java", tmp_path / "logisim.jar", project, program, output)

    assert commands[0][-3:-1] == ["-tty", "table,halt"]
    assert output.read_text(encoding="utf-8") == raw_table


def test_tty_trace_converter_samples_last_stable_low_row_per_edge():
    raw = "\n".join(
        [
            "Logisim-evolution v4.1.0",
            _tty_row(PRINT_VALUE="UUUUUUUUUUUUUUUU", TRACE_CLK="0"),
            _tty_row(PRINT_VALUE="0000000000000111", TRACE_CLK="0"),
            _tty_row(PRINT_VALUE="0000000000000111", TRACE_CLK="1"),
            _tty_row(PRINT_ENABLE="1", PRINT_VALUE="0000000000000111", TRACE_CLK="0"),
            _tty_row(PRINT_ENABLE="1", PRINT_VALUE="0000000000000111", TRACE_CLK="1"),
            _tty_row(HALT_ENABLE="1", HALTED="1", halt="1", TRACE_CLK="0"),
        ]
    )

    converted = runner._tty_trace_to_tsv(raw)

    assert len(converted.splitlines()) == 4
    assert "\t7\t" in converted


def test_run_retains_simulator_stdout_before_reporting_failure(tmp_path, monkeypatch):
    """A failed electrical comparison must still leave useful CI evidence."""
    output = tmp_path / "artifacts" / "trace.tsv"
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, "PIN_A\tPIN_B\n0\t1\n", "simulator failed\n"
        ),
    )

    try:
        runner._run(["logisim"], stdout_path=output)
    except runner.SmokeTestError:
        pass
    else:
        raise AssertionError("a failed simulator process was accepted")

    assert output.read_text(encoding="utf-8") == "PIN_A\tPIN_B\n0\t1\n"


def test_run_retains_partial_stdout_when_simulator_times_out(tmp_path, monkeypatch):
    """A timeout must preserve the electrical rows emitted before the hang."""
    output = tmp_path / "artifacts" / "trace.tsv"

    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], kwargs["timeout"], output="HEADER\npartial row\n"
        )

    monkeypatch.setattr(runner.subprocess, "run", time_out)

    try:
        runner._run(["logisim"], stdout_path=output)
    except runner.SmokeTestError:
        pass
    else:
        raise AssertionError("a timed-out simulator process was accepted")

    assert output.read_text(encoding="utf-8") == "HEADER\npartial row\n"


def test_main_creates_diagnostic_artifact_before_dependency_checks(tmp_path, monkeypatch):
    """Even a Java/version failure must not make the upload step fail again."""
    output = tmp_path / "artifacts" / "trace.tsv"

    def fail_java(java):
        raise runner.SmokeTestError("wrong Java")

    monkeypatch.setattr(runner, "verify_java", fail_java)

    assert runner.main(["--trace-output", str(output)]) == 1
    assert "has not reached the simulator" in output.read_text(encoding="utf-8")


def test_ci_publishes_the_raw_electrical_trace_even_on_failure():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "--acceptance-output artifacts/ci/tinycpu-ap12-acceptance" in workflow
    assert "name: tinycpu-ap12-electrical-acceptance" in workflow
    assert "if: always()" in workflow
    assert "uses: actions/upload-artifact@v5" in workflow
    assert "path: artifacts/ci/" in workflow
    assert "actions/upload-artifact@v4" not in workflow


def test_ap12_acceptance_repeats_trace_and_runs_complete_matrix(tmp_path, monkeypatch):
    """The release command must make lifecycle and ISA checks inseparable."""
    calls = []

    def fake_trace(java, jar, project, program, output):
        calls.append(("trace", output.name))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("raw simulator output\n", encoding="utf-8")
        return "PRINT_VALID\tPRINT_VALUE\n0\t0\n"

    def fake_matrix(java, jar, project, matrix_path, output):
        calls.append(("matrix", output.name))
        output.mkdir(parents=True)

    monkeypatch.setattr(runner, "trace_test", fake_trace)
    monkeypatch.setattr(runner, "matrix_test", fake_matrix)
    output = tmp_path / "acceptance"

    runner.acceptance_test(
        "java",
        tmp_path / "logisim.jar",
        runner.DEFAULT_PROJECT,
        runner.DEFAULT_PROGRAM,
        runner.DEFAULT_MATRIX,
        output,
    )

    assert calls == [
        ("trace", "reset-start.tsv"),
        ("trace", "restart.tsv"),
        ("matrix", "isa-matrix"),
    ]
    import json

    report = json.loads((output / "acceptance.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == 2
    assert report["status"] == "passed"
    assert report["reset_restart_runs"][0]["clock_edges"] == 1
    assert report["reset_restart_runs"][0]["sha256"] == report["reset_restart_runs"][1]["sha256"]
    assert [item["path"] for item in report["evidence"]] == [
        "reset-start.normalized.tsv",
        "reset-start.tsv",
        "restart.normalized.tsv",
        "restart.tsv",
    ]
    for item in report["evidence"]:
        evidence_path = output / item["path"]
        assert item["size_bytes"] == evidence_path.stat().st_size
        assert item["sha256"] == runner.hashlib.sha256(evidence_path.read_bytes()).hexdigest()


def test_ap12_acceptance_rejects_nonreproducible_restart(tmp_path, monkeypatch):
    traces = iter(("HEADER\nfirst\n", "HEADER\nsecond\n"))

    def fake_trace(java, jar, project, program, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("raw\n", encoding="utf-8")
        return next(traces)

    monkeypatch.setattr(runner, "trace_test", fake_trace)
    try:
        runner.acceptance_test(
            "java", tmp_path / "jar", runner.DEFAULT_PROJECT,
            runner.DEFAULT_PROGRAM, runner.DEFAULT_MATRIX, tmp_path / "out"
        )
    except runner.SmokeTestError as exc:
        assert "not reproducible" in str(exc)
    else:
        raise AssertionError("different restart traces were accepted")


def _acceptance_bundle(path):
    import hashlib
    import json

    files = {
        "isa-matrix/data.tsv": b"matrix evidence\n",
        "reset-start.normalized.tsv": b"normalized evidence\n",
        "reset-start.tsv": b"electrical evidence\n",
        "restart.normalized.tsv": b"normalized evidence\n",
        "restart.tsv": b"electrical evidence\n",
    }
    evidence = []
    for name, contents in files.items():
        evidence_path = path / name
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_bytes(contents)
        evidence.append({"path": name, "sha256": hashlib.sha256(contents).hexdigest(),
                         "size_bytes": len(contents)})
    trace_digest = hashlib.sha256(files["reset-start.normalized.tsv"]).hexdigest()
    report = {
        "schema_version": 2,
        "status": "passed",
        "logisim_version": runner.LOGISIM_VERSION,
        "java_version": runner.JAVA_VERSION,
        "reset_restart_runs": [
            {"name": name, "raw_table": f"{name}.tsv",
             "normalized_table": f"{name}.normalized.tsv",
             "sha256": trace_digest, "clock_edges": 1}
            for name in ("reset-start", "restart")
        ],
        "matrix": {"fixture_count": 1, "directory": "isa-matrix"},
        "evidence": evidence,
    }
    (path / "acceptance.json").write_text(json.dumps(report), encoding="utf-8")
    return path / "reset-start.tsv"


def test_ap12_bundle_verifier_accepts_complete_untampered_inventory(tmp_path):
    _acceptance_bundle(tmp_path)

    runner.verify_acceptance_bundle(tmp_path)


def test_ap12_bundle_verifier_rejects_tampered_evidence(tmp_path):
    evidence = _acceptance_bundle(tmp_path)
    evidence.write_text("modified evidence\n", encoding="utf-8")

    try:
        runner.verify_acceptance_bundle(tmp_path)
    except runner.SmokeTestError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("tampered AP-12 evidence was accepted")


def test_ap12_bundle_verifier_rejects_symbolic_link_evidence(tmp_path):
    evidence = _acceptance_bundle(tmp_path)
    external = tmp_path.parent / "external-electrical-evidence.tsv"
    external.write_bytes(evidence.read_bytes())
    evidence.unlink()
    evidence.symlink_to(external)

    try:
        runner.verify_acceptance_bundle(tmp_path)
    except runner.SmokeTestError as exc:
        assert "symbolic link" in str(exc)
    else:
        raise AssertionError("symbolic-link AP-12 evidence was accepted")


def test_ap12_bundle_verifier_rejects_non_object_report(tmp_path):
    (tmp_path / "acceptance.json").write_text("[]", encoding="utf-8")

    try:
        runner.verify_acceptance_bundle(tmp_path)
    except runner.SmokeTestError as exc:
        assert "must be a JSON object" in str(exc)
    else:
        raise AssertionError("non-object AP-12 report was accepted")


def test_ap12_bundle_verifier_rejects_malformed_inventory_metadata(tmp_path):
    import json

    _acceptance_bundle(tmp_path)
    report_path = tmp_path / "acceptance.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    invalid_values = (
        ("path", "./reset-start.tsv", "unsafe AP-12 evidence path"),
        ("size_bytes", True, "invalid AP-12 evidence size"),
        ("sha256", "not-a-sha256", "invalid AP-12 evidence digest"),
    )
    for field, value, message in invalid_values:
        invalid = json.loads(json.dumps(report))
        invalid["evidence"][0][field] = value
        report_path.write_text(json.dumps(invalid), encoding="utf-8")
        try:
            runner.verify_acceptance_bundle(tmp_path)
        except runner.SmokeTestError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"malformed AP-12 {field} was accepted")


def test_ap12_bundle_verifier_rejects_incomplete_acceptance_metadata(tmp_path):
    import json

    _acceptance_bundle(tmp_path)
    report_path = tmp_path / "acceptance.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    invalid_reports = (
        ({**report, "logisim_version": "untrusted"}, "invalid Logisim version"),
        ({**report, "reset_restart_runs": report["reset_restart_runs"][:1]},
         "two reset/restart runs"),
        ({**report, "matrix": {"fixture_count": 2, "directory": "isa-matrix"}},
         "fixture count"),
    )
    for invalid, message in invalid_reports:
        report_path.write_text(json.dumps(invalid), encoding="utf-8")
        try:
            runner.verify_acceptance_bundle(tmp_path)
        except runner.SmokeTestError as exc:
            assert message in str(exc)
        else:
            raise AssertionError("incomplete AP-12 acceptance metadata was accepted")


def test_verify_acceptance_cli_skips_simulator_dependencies(tmp_path, monkeypatch):
    _acceptance_bundle(tmp_path)

    def unexpected_java(java):
        raise AssertionError("offline verification invoked Java")

    monkeypatch.setattr(runner, "verify_java", unexpected_java)
    assert runner.main(["--verify-acceptance", str(tmp_path)]) == 0


def test_ci_uses_available_temurin_build_and_current_setup_action():
    """Keep the pinned JDK resolvable and avoid setup-java's Node 20 runtime."""
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "uses: actions/setup-java@v5" in workflow
    assert "java-version: '21.0.8+9.0.LTS'" in workflow
    assert "actions/setup-java@v4" not in workflow
    assert "uses: actions/checkout@v5" in workflow
    assert "uses: actions/setup-python@v6" in workflow


def test_ap11_matrix_contract_covers_every_opcode_and_sticky_error():
    runner.verify_matrix_contract(runner.DEFAULT_MATRIX, runner.DEFAULT_MACHINE_FORMAT)


def test_ap11_matrix_supplies_runnable_family_and_error_fixtures():
    import json

    matrix = json.loads(runner.DEFAULT_MATRIX.read_text(encoding="utf-8"))
    expected = {family["id"] for family in matrix["opcode_families"]}
    expected.update(row["fixture"] for row in matrix["sticky_errors"])

    assert {fixture["id"] for fixture in matrix["fixtures"]} == expected
    assert all(fixture["program"].strip() for fixture in matrix["fixtures"])


def test_ap11_matrix_contract_rejects_missing_opcode(tmp_path):
    import json

    matrix = json.loads(runner.DEFAULT_MATRIX.read_text(encoding="utf-8"))
    matrix["opcode_families"][0]["opcodes"].pop()
    incomplete = tmp_path / "matrix.json"
    incomplete.write_text(json.dumps(matrix), encoding="utf-8")

    try:
        runner.verify_matrix_contract(incomplete, runner.DEFAULT_MACHINE_FORMAT)
    except runner.SmokeTestError as exc:
        assert "missing:" in str(exc)
    else:
        raise AssertionError("an incomplete electrical opcode matrix was accepted")


def test_ap11_matrix_contract_rejects_duplicate_error_fixture(tmp_path):
    import json

    matrix = json.loads(runner.DEFAULT_MATRIX.read_text(encoding="utf-8"))
    matrix["sticky_errors"].append(matrix["sticky_errors"][0])
    invalid = tmp_path / "matrix.json"
    invalid.write_text(json.dumps(matrix), encoding="utf-8")

    try:
        runner.verify_matrix_contract(invalid, runner.DEFAULT_MACHINE_FORMAT)
    except runner.SmokeTestError as exc:
        assert "each sticky error exactly once" in str(exc)
    else:
        raise AssertionError("duplicate sticky-error coverage was accepted")
