"""Tests for the pinned real-Logisim TinyCPU smoke-test runner."""

import csv
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest

import tiny_cpu_logisim as runner


CI_WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"


def completed(command: list[str], stdout: str = "", stderr: str = ""):
    """Build a successful subprocess result for the small command doubles."""
    return subprocess.CompletedProcess(command, 0, stdout, stderr)


def subcircuit_output(root, circuit_name: str, pin_label: str) -> str:
    """Resolve a generated-symbol output without freezing drawing coordinates."""
    definition = root.find(f"circuit[@name='{circuit_name}']")
    assert definition is not None
    outputs = sorted(
        (
            component
            for component in definition.findall("comp[@name='Pin']")
            if runner._pin_attributes(component).get("type") == "output"
        ),
        key=lambda component: tuple(
            int(value) for value in component.get("loc").strip("()").split(",")
        )[::-1],
    )
    output_index = next(
        index
        for index, component in enumerate(outputs)
        if runner._pin_attributes(component).get("label") == pin_label
    )
    main = root.find("circuit[@name='TinyCPUMain']")
    assert main is not None
    instance = next(
        component
        for component in main.findall("comp")
        if component.get("name") == circuit_name
    )
    x, y = (int(value) for value in instance.get("loc").strip("()").split(","))
    return f"({x},{y + 20 * output_index})"


def test_verify_java_accepts_supported_newer_runtimes(monkeypatch):
    """Patch-level drift must not prevent running the real simulator locally."""
    monkeypatch.setattr(
        runner,
        "_run",
        lambda command: completed(command, stderr='openjdk version "21.0.8" 2025-07-15\n'),
    )
    runner.verify_java("java")

    monkeypatch.setattr(
        runner,
        "_run",
        lambda command: completed(command, stderr='openjdk version "25.0.2" 2026-01-20\n'),
    )
    runner.verify_java("java")

    monkeypatch.setattr(
        runner,
        "_run",
        lambda command: completed(command, stderr='openjdk version "17.0.16" 2025-07-15\n'),
    )
    try:
        runner.verify_java("java")
    except runner.SmokeTestError as exc:
        assert "Java 21 or newer is required; found 17.0.16" in str(exc)
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
    values = {
        label: "0" * width if width > 1 else "0"
        for label, width in runner.TTY_OUTPUTS
    }
    values.update(overrides)
    tokens = []
    for label, width in runner.TTY_OUTPUTS:
        value = values[label]
        tokens.extend(
            [value[index : index + 4] for index in range(0, width, 4)]
            if width > 1 else [value]
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
        '<comp name="Splitter" loc="(10,40)"><a name="incoming" val="22"/></comp>'
        '<wire from="(0,0)" to="(10,0)"/>'
        '<wire from="(0,40)" to="(10,40)"/>'
        '<wire from="(890,390)" to="(930,390)"/>'
        '</circuit><circuit name="FetchDecode"><comp name="ROM">'
        '<a name="contents">addr/data: 12 22\n2c0000\n</a>'
        "</comp></circuit></project>",
        encoding="utf-8",
    )
    program = tmp_path / "program.tcpu"
    program.write_text("HALT()\n", encoding="utf-8")
    output = tmp_path / "artifacts" / "trace.tsv"
    raw_table = _tty_row(TRACE_OPCODE=f"{44:06b}" + "0" * 16, HALTED="1") + "\n"
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


def test_trace_test_explains_a_premature_normal_halt(tmp_path, monkeypatch):
    project = tmp_path / "TinyCPU.circ"
    project.write_text(
        '<?xml version="1.0"?><project><main name="TinyCPUMain"/>'
        '<circuit name="TinyCPUMain">'
        '<comp name="Pin" loc="(0,0)"><a name="label" val="CLK"/></comp>'
        '<comp name="Pin" loc="(0,20)"><a name="label" val="RESET"/></comp>'
        '<comp name="Splitter" loc="(10,40)"><a name="incoming" val="22"/></comp>'
        '<wire from="(0,0)" to="(10,0)"/>'
        '<wire from="(0,40)" to="(10,40)"/>'
        '<wire from="(890,390)" to="(930,390)"/>'
        '</circuit><circuit name="FetchDecode"><comp name="ROM">'
        '<a name="contents">addr/data: 12 22\n2c0000\n</a>'
        "</comp></circuit></project>",
        encoding="utf-8",
    )
    program = tmp_path / "program.tcpu"
    program.write_text("LOAD_CONST(1)\nHALT()\n", encoding="utf-8")
    raw_table = _tty_row(
        TRACE_OPCODE=f"{44:06b}" + "0" * 16,
        HALTED="1",
    ) + "\n"
    monkeypatch.setattr(
        runner,
        "_run",
        lambda command, **kwargs: completed(command, stdout=raw_table),
    )

    with pytest.raises(runner.SmokeTestError) as caught:
        runner.trace_test(
            "java", tmp_path / "logisim.jar", project, program, tmp_path / "trace.tsv"
        )

    message = str(caught.value)
    assert "halted normally after 1 clock edges; expected 2" in message
    assert "first mismatch:" in message


def test_autonomous_trace_taps_real_tinycpu_main_nets():
    """Trace probes must not silently sit on empty drawing coordinates."""

    tree = ET.parse(runner.DEFAULT_PROJECT)
    main = tree.getroot().find("circuit[@name='TinyCPUMain']")
    assert main is not None
    trace_tree = ET.parse(runner.DEFAULT_PROJECT)
    runner._autonomous_trace_project(trace_tree)
    trace_main = trace_tree.getroot().find("circuit[@name='TinyCPUMain']")
    assert trace_main is not None
    # The harness must tap the gate's real input terminals without drawing a
    # vertical route across the adjacent public halt outputs.  That former
    # route shorted normal and error halt together at the crossing endpoint.
    halt_tunnels = {
        runner._pin_attributes(component).get("label"): set()
        for component in trace_main.findall("comp[@name='Tunnel']")
        if runner._pin_attributes(component).get("label", "").startswith("AP5_HALT_")
    }
    for component in trace_main.findall("comp[@name='Tunnel']"):
        label = runner._pin_attributes(component).get("label")
        if label in halt_tunnels:
            halt_tunnels[label].add(component.get("loc"))
    assert halt_tunnels == {
        "AP5_HALT_NORMAL": {"(3330,1650)", "(3470,1900)"},
        "AP5_HALT_ERROR": {"(3330,1670)", "(3470,1940)"},
    }
    original_wires = {
        (wire.get("from"), wire.get("to")) for wire in main.findall("wire")
    }

    opcode_probe = next(
        component.get("loc")
        for component in main.findall("comp[@name='Splitter']")
        if runner._pin_attributes(component).get("incoming") == "22"
    )
    clock_pin = next(
        component.get("loc")
        for component in main.findall("comp[@name='Pin']")
        if runner._pin_attributes(component).get("label") == "CLK"
    )
    clock_probe = next(
        end if start == clock_pin else start
        for start, end in original_wires
        if clock_pin in {start, end}
    )

    runner._autonomous_trace_project(tree)

    expected_probes = {opcode_probe, clock_probe}
    tunnels = {
        runner._pin_attributes(component).get("label"): (
            component.get("loc"), runner._pin_attributes(component).get("width")
        )
        for component in main.findall("comp[@name='Tunnel']")
        if component.get("loc") in expected_probes
    }
    assert tunnels == {
        "AP5_TRACE_OPCODE": (opcode_probe, "22"),
        "AP5_TRACE_CLOCK": (clock_probe, None),
    }

    # Each source probe is an endpoint or junction of the maintained circuit,
    # rather than merely being present somewhere on the drawing canvas.
    contacts = {point for wire in original_wires for point in wire}
    assert {location for location, _width in tunnels.values()} <= contacts

    generated_wires = {
        (wire.get("from"), wire.get("to")) for wire in main.findall("wire")
    }
    output_locations = {
        runner._pin_attributes(component).get("label"): component.get("loc")
        for component in main.findall("comp[@name='Pin']")
        if runner._pin_attributes(component).get("type") == "output"
    }
    halted = output_locations["HALTED"]
    halted_with_error = output_locations["HALTED_WITH_ERROR"]
    assert not any(halted in wire for wire in generated_wires - original_wires)
    assert not any(halted_with_error in wire for wire in generated_wires - original_wires)
    assert any(
        component.get("name") == "OR Gate"
        and runner._pin_attributes(component).get("label") == "HALT_ANY"
        for component in main.findall("comp")
    )
    print_enable = subcircuit_output(
        tree.getroot(), "FetchDecodeControls", "PRINT"
    )
    # The redrawn control block reaches the public output through a visible
    # dog-leg.  Follow the maintained wire contacts instead of requiring the
    # obsolete single-segment route from the former symbol position.
    adjacency: dict[str, set[str]] = {}
    for start, end in original_wires:
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)
    reachable = {print_enable}
    pending = [print_enable]
    while pending:
        point = pending.pop()
        for neighbor in adjacency.get(point, ()):
            if neighbor not in reachable:
                reachable.add(neighbor)
                pending.append(neighbor)
    assert output_locations["PRINT_ENABLE"] in reachable


def test_tty_output_order_follows_generated_symbol_pin_positions():
    """A compact redraw must not shift tty values into obsolete columns."""

    tree = ET.parse(runner.DEFAULT_PROJECT)
    runner._autonomous_trace_project(tree)
    main = tree.getroot().find("circuit[@name='TinyCPUMain']")
    assert main is not None

    order = runner._tty_output_order(main)

    assert order[0] == ("PRINT_VALUE", 16)
    assert order[1:4] == (
        ("PRINT_ADDRESS_VALID", 1),
        ("PRINT_ADDRESS_VALUE", 16),
        ("PRINT_VALID", 1),
    )
    assert order[-3:] == (
        ("TRACE_PC", 12),
        ("TRACE_OPCODE", 22),
        ("TRACE_CLK", 1),
    )


def test_tty_trace_converter_samples_last_stable_low_row_per_edge():
    raw = "\n".join(
        [
            "Logisim-evolution v4.1.0",
            _tty_row(PRINT_VALUE="UUUUUUUUUUUUUUUU", TRACE_PC=f"{0:012b}", TRACE_CLK="0"),
            _tty_row(PRINT_VALUE="0000000000000111", TRACE_PC=f"{0:012b}", TRACE_CLK="0"),
            _tty_row(PRINT_VALUE="0000000000000111", TRACE_PC=f"{0:012b}", TRACE_CLK="1"),
            _tty_row(PRINT_ENABLE="1", PRINT_VALUE="0000000000000111", TRACE_PC=f"{1:012b}", TRACE_CLK="0"),
            _tty_row(PRINT_ENABLE="1", PRINT_VALUE="0000000000000111", TRACE_PC=f"{1:012b}", TRACE_CLK="1"),
            _tty_row(TRACE_PC=f"{2:012b}", TRACE_OPCODE=f"{44:06b}" + "0" * 16, HALTED="1", TRACE_CLK="0"),
        ]
    )

    converted = runner._tty_trace_to_tsv(raw)

    assert len(converted.splitlines()) == 4
    assert "\t7\t" in converted


def test_tty_trace_converter_reports_undefined_fetch_decode_state():
    raw = _tty_row(TRACE_OPCODE="U" * 22)

    try:
        runner._tty_trace_to_tsv(raw)
    except runner.SmokeTestError as exc:
        message = str(exc)
        assert "fetch/decode is undefined" in message
        assert "TRACE_OPCODE=" in message
    else:
        raise AssertionError("undefined PC/opcode state was accepted")


def test_tty_trace_converter_preserves_error_halt_asserted_on_final_rising_edge():
    raw = "\n".join(
        [
            _tty_row(TRACE_CLK="0"),
            _tty_row(ERROR_INV="1", HALTED_WITH_ERROR="1", TRACE_CLK="1"),
        ]
    )

    converted = runner._tty_trace_to_tsv(raw)

    row = list(csv.DictReader(converted.splitlines(), delimiter="\t"))[0]
    assert row["ERROR_INV"] == "1"
    assert row["HALTED_WITH_ERROR"] == "1"


def test_tty_trace_converter_records_hex_states_and_rejects_loop():
    machine_word = f"{5:06b}" + f"{7:016b}"
    raw = "\n".join(
        [
            _tty_row(TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="0"),
            _tty_row(TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="1"),
            _tty_row(TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="0"),
            _tty_row(TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="1"),
        ]
    )
    execution_map = {}

    with pytest.raises(runner.SmokeTestError, match="execution loop detected"):
        runner._tty_trace_to_tsv(raw, execution_map)

    assert execution_map.keys() == {"0x003"}
    assert len(execution_map["0x003"]) == 1
    assert next(iter(execution_map["0x003"])).startswith("0x")


def test_tty_trace_converter_allows_same_instruction_with_changed_state():
    machine_word = f"{5:06b}" + f"{7:016b}"
    raw = "\n".join(
        [
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=f"{1:016b}",
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="0",
            ),
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=f"{1:016b}",
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="1",
            ),
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=f"{2:016b}",
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="0",
            ),
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=f"{2:016b}",
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="1",
            ),
        ]
    )
    execution_map = {}

    runner._tty_trace_to_tsv(raw, execution_map)

    assert len(execution_map["0x003"]) == 2


@pytest.mark.parametrize("electrical_value", ["U", "E"])
def test_tty_trace_converter_rejects_loops_with_four_state_values(electrical_value):
    """Undefined and error-valued buses must still participate in loop detection."""
    machine_word = f"{5:06b}" + f"{7:016b}"
    state = electrical_value * 16
    raw = "\n".join(
        [
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=state,
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="0",
            ),
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=state,
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="1",
            ),
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=state,
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="0",
            ),
            _tty_row(
                PRINT_ENABLE="1", PRINT_VALUE=state,
                TRACE_PC=f"{3:012b}", TRACE_OPCODE=machine_word, TRACE_CLK="1",
            ),
        ]
    )

    with pytest.raises(runner.SmokeTestError, match="execution loop detected"):
        runner._tty_trace_to_tsv(raw, {})


def test_four_state_loop_fingerprint_distinguishes_undefined_from_error():
    """U and E are separate electrical states rather than one unknown bucket."""
    base = {
        label: "0" * width if width > 1 else "0"
        for label, width in runner.TTY_OUTPUTS
    }
    undefined = {**base, "PRINT_ENABLE": "1", "PRINT_VALUE": "U" * 16}
    error = {**base, "PRINT_ENABLE": "1", "PRINT_VALUE": "E" * 16}

    assert runner._four_state_hex(undefined) != runner._four_state_hex(error)


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


def test_run_treats_logisim_halt_message_as_normal_completion(monkeypatch, capsys):
    """Logisim logs its expected halt-pin exit at ERROR level despite status zero."""
    marker = (
        "[main] ERROR com.cburch.logisim.gui.start.TtyInterface - "
        "halted due to halt pin\n"
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "table\n", marker),
    )

    runner._run(["logisim"])

    captured = capsys.readouterr()
    assert "stopped at the configured halt pin" in captured.out
    assert captured.err == ""


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


def test_ci_runs_complete_electrical_opcode_acceptance():
    """Every CI test run must repeat the inseparable electrical ISA proof."""
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "run: scripts/test-logisim.sh" in workflow
    assert "Load TinyCPU in pinned Logisim-evolution" not in workflow


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


def test_opcode_proof_matrix_supplies_dedicated_cases_and_error_fixtures():
    import json

    matrix = json.loads(runner.DEFAULT_MATRIX.read_text(encoding="utf-8"))
    expected = {case["id"] for case in matrix["opcode_cases"]}
    expected.update(row["fixture"] for row in matrix["sticky_errors"])

    fixtures = [*matrix["opcode_cases"], *matrix["fixtures"]]
    assert {fixture["id"] for fixture in fixtures} == expected
    assert all(fixture["program"].strip() for fixture in fixtures)


def test_ap11_matrix_contract_rejects_missing_opcode(tmp_path):
    import json

    matrix = json.loads(runner.DEFAULT_MATRIX.read_text(encoding="utf-8"))
    matrix["opcode_cases"] = [
        case for case in matrix["opcode_cases"] if case["opcode"] != "LOAD_CONST"
    ]
    incomplete = tmp_path / "matrix.json"
    incomplete.write_text(json.dumps(matrix), encoding="utf-8")

    try:
        runner.verify_matrix_contract(incomplete, runner.DEFAULT_MACHINE_FORMAT)
    except runner.SmokeTestError as exc:
        assert "missing:" in str(exc)
    else:
        raise AssertionError("an incomplete electrical opcode matrix was accepted")


def test_opcode_proof_contract_rejects_disabling_each_dedicated_case(tmp_path):
    """Every opcode must own a case whose removal invalidates the matrix."""
    import json

    matrix = json.loads(runner.DEFAULT_MATRIX.read_text(encoding="utf-8"))
    opcodes = {case["opcode"] for case in matrix["opcode_cases"]}
    for opcode in opcodes:
        mutated = dict(matrix)
        mutated["opcode_cases"] = [
            case for case in matrix["opcode_cases"] if case["opcode"] != opcode
        ]
        path = tmp_path / f"without-{opcode}.json"
        path.write_text(json.dumps(mutated), encoding="utf-8")
        try:
            runner.verify_matrix_contract(path, runner.DEFAULT_MACHINE_FORMAT)
        except runner.SmokeTestError as exc:
            assert f"missing: {opcode}" in str(exc)
        else:
            raise AssertionError(f"matrix accepted without {opcode}")


def test_opcode_proof_jump_cases_make_taken_and_fallthrough_paths_observable():
    import json

    matrix = json.loads(runner.DEFAULT_MATRIX.read_text(encoding="utf-8"))
    jumps = [case for case in matrix["opcode_cases"] if case["opcode"].startswith("JUMP_")]
    unconditional = next(case for case in jumps if case["opcode"] == "JUMP_ADDRESS")
    assert unconditional["program"].splitlines()[1] == "HALT_ERROR()"
    for opcode in ("JUMP_ZERO", "JUMP_NOT_ZERO", "JUMP_NEGATIVE", "JUMP_ERROR", "JUMP_NOT_ERROR"):
        variants = {case["variant"]: case for case in jumps if case["opcode"] == opcode}
        assert set(variants) == {"taken", "not-taken"}
        assert "HALT_ERROR()" in variants["taken"]["program"]
        assert variants["not-taken"]["program"].splitlines()[-1] == "HALT_ERROR()"


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
