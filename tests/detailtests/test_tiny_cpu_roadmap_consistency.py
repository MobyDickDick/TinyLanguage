"""Keep the high-level TinyCPU roadmap aligned with its acceptance checklist."""

import json
import re
import subprocess
from pathlib import Path

from tiny_cpu_isa import INSTRUCTION_SET


REPOSITORY_ROOT = Path(__file__).parents[2]


def test_user_guide_and_roadmap_record_verified_tinycpu_completeness():
    """Accepted wiring and ISA coverage must not read like future build work."""

    user_guide = (REPOSITORY_ROOT / "docs" / "tiny_cpu.md").read_text(
        encoding="utf-8"
    )
    roadmap = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    machine = json.loads(
        (REPOSITORY_ROOT / "hardware" / "logisim" / "tinycpu-machine-v1.json")
        .read_text(encoding="utf-8")
    )

    machine_opcodes = {entry["mnemonic"] for entry in machine["opcodes"]}
    assert machine_opcodes == set(INSTRUCTION_SET)
    assert len(machine["opcodes"]) == 50
    assert "### Abgenommener Aufbau in Logisim-evolution" in user_guide
    assert "`TinyCPUMain: connected`" in user_guide
    assert "alle 50\nOpcodes" in user_guide
    assert (
        "beschreibt die bereits ausgeführte Aufbau- und\nAbnahmereihenfolge"
        in user_guide
    )
    assert "### Empfohlener Aufbau in Logisim-evolution" not in user_guide
    assert "unabhängig von\n  der noch fehlenden Verdrahtung" not in roadmap
    assert (
        "## Abgeschlossener Folgeschritt: elektrische Top-Level-Integration"
        in roadmap
    )


def test_expansion_roadmap_does_not_reopen_completed_hardware_packages():
    """Every completed AP must stay closed when no next package is scoped."""

    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    expansion = (REPOSITORY_ROOT / "docs" / "expansion_roadmap.md").read_text(
        encoding="utf-8"
    )

    defined_packages = [
        (int(package), title)
        for package, title in re.findall(
            r"^\| \*\*(\d+)\. ([^*]+)\*\*", detailed, re.MULTILINE
        )
    ]
    completed_packages = [
        (int(package), title)
        for package, title in re.findall(
            r"^- \[x\] \*\*AP (\d+): ([^*]+):\*\*",
            detailed,
            re.MULTILINE,
        )
    ]
    assert [package for package, _ in defined_packages] == list(range(1, 16))
    assert [package for package, _ in completed_packages] == list(range(1, 16))
    assert defined_packages == completed_packages

    completed_package_heading = re.search(
        r"^## Abgeschlossenes Arbeitspaket: AP (\d+) – (.+)$",
        detailed,
        re.MULTILINE,
    )
    assert completed_package_heading is not None
    highlighted_package = (
        int(completed_package_heading.group(1)),
        completed_package_heading.group(2),
    )
    assert highlighted_package == completed_packages[11]

    tinycpu_section = expansion.split("## 1) Native compiler", maxsplit=1)[0]
    assert "**Completed boundary**: AP 1 through AP 12 are complete" in tinycpu_section
    assert "completed AP 13 through AP 15 release sequence" in tinycpu_section
    assert "active\n  maintenance history" not in tinycpu_section
    assert "No successor package is\n  currently scoped" in tinycpu_section
    assert "add a mandatory headless" not in tinycpu_section

    active_boundary = detailed.split(
        "## Abgeschlossene Release-Arbeitspaketgrenze", maxsplit=1
    )[1].split("## Abgeschlossene Baseline-Pflege", maxsplit=1)[0]
    assert "AP 13 hat die\nRelease-Grenze eingefroren" in active_boundary
    assert "AP 15 deren signierte Clean-Room-Qualifikation" in active_boundary
    assert "[TinyCPU-1.0-Releaseplan]" in active_boundary


def test_active_backlog_exposes_the_scoped_tinycpu_release_package():
    """The active backlog and roadmaps must identify the same next package."""

    active_tasks = (REPOSITORY_ROOT / "docs" / "open_tasks.md").read_text(
        encoding="utf-8"
    ).split("## Open-task audit", maxsplit=1)[0]
    expansion = (REPOSITORY_ROOT / "docs" / "expansion_roadmap.md").read_text(
        encoding="utf-8"
    )

    unchecked_tinycpu = re.findall(
        r"^- \[ \] \*\*[^\n]*(?:TinyCPU|Tiny CPU)[^\n]*",
        active_tasks,
        re.IGNORECASE | re.MULTILINE,
    )
    assert unchecked_tinycpu == []

    tinycpu_section = expansion.split("## 1) Native compiler", maxsplit=1)[0]
    assert "No successor package is\n  currently scoped" in tinycpu_section
    assert "Re-validate the TinyCPU work-package boundary" in active_tasks
    assert "there is no unchecked TinyCPU package to implement" in active_tasks
    assert (
        "new TinyCPU work must first be added here as a bounded,\n"
        "    unchecked package with acceptance criteria"
        in active_tasks
    )
    assert "Reconcile stale TinyCPU follow-up notes" in active_tasks
    assert "Freeze the restored TinyCPU jump-operand route" in active_tasks
    assert "Freeze TinyCPU next-PC selector net isolation" in active_tasks
    assert (
        "Complete TinyCPU next-PC selector pairwise isolation coverage"
        in active_tasks
    )

    user_guide = (REPOSITORY_ROOT / "docs" / "tiny_cpu.md").read_text(
        encoding="utf-8"
    )
    hardware_readme = (
        REPOSITORY_ROOT / "hardware" / "logisim" / "README.md"
    ).read_text(encoding="utf-8")
    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    stale_completion_claims = (
        "Assembler erzeugt noch **kein binäres ROM-Abbild**",
        "weiterhin sichtbare, zu kurze Schleifenausführung",
        "Als nächster externer Abnahmeschritt bleibt",
    )
    combined_docs = user_guide + hardware_readme + detailed
    for claim in stale_completion_claims:
        assert claim not in combined_docs


def test_active_task_history_starts_with_a_complete_work_package():
    """A removed package must not leave wrapped prose below the section heading."""

    active_tasks = (REPOSITORY_ROOT / "docs" / "open_tasks.md").read_text(
        encoding="utf-8"
    )
    current_tasks = active_tasks.split("## Current tasks", maxsplit=1)[1]
    first_content_line = next(
        line for line in current_tasks.splitlines() if line.strip()
    )

    assert re.match(r"^- \[[ x]\] \*\*", first_content_line)
    assert first_content_line.endswith("**")


def test_completed_release_entries_do_not_advertise_ap15_as_active():
    """Earlier release entries must agree that the AP-15 sequence is closed."""

    active_tasks = (REPOSITORY_ROOT / "docs" / "open_tasks.md").read_text(
        encoding="utf-8"
    )
    release_history = active_tasks.split(
        "**AP 13: Freeze the TinyCPU 1.0 release contract**", maxsplit=1
    )[1].split(
        "**Finish making the TinyCPU trace regression redraw-aware**", maxsplit=1
    )[0]

    assert "AP 15 is now active" not in release_history
    assert "AP 15 is complete" in release_history
    assert "no successor release package is currently\n    scoped" in release_history


def test_latest_tinycpu_audit_does_not_invent_a_successor_package():
    """Completed maintenance history is not an implicit hardware backlog."""

    active_tasks = (REPOSITORY_ROOT / "docs" / "open_tasks.md").read_text(
        encoding="utf-8"
    )
    latest_package = active_tasks.split(
        "**Confirm the TinyCPU work-package boundary after task-log repair**",
        maxsplit=1,
    )[1].split("- [x] **Repair the TinyCPU active-task boundary**", maxsplit=1)[0]

    assert "AP 1 through AP 12" in latest_package
    assert "no documented implementation package to execute" in latest_package
    assert "no\n    hardware change is warranted" in latest_package
    assert "bounded, unchecked item with acceptance criteria" in latest_package


def test_post_repair_audit_keeps_the_tinycpu_backlog_closed():
    """The electrical repair must not be mistaken for new feature scope."""

    active_tasks = (REPOSITORY_ROOT / "docs" / "open_tasks.md").read_text(
        encoding="utf-8"
    )
    latest_package = active_tasks.split(
        "**Re-confirm the TinyCPU work-package boundary after electrical repair**",
        maxsplit=1,
    )[1].split(
        "- [x] **Restore TinyCPU electrical acceptance after the latest redraw**",
        maxsplit=1,
    )[0]

    assert "AP 1 through AP 15 remain complete" in latest_package
    assert "no unchecked TinyCPU package to\n    implement" in latest_package
    assert (
        "no circuit, release-contract, or feature change\n    is warranted"
        in latest_package
    )
    assert (
        "bounded,\n    unchecked package with explicit acceptance criteria"
        in latest_package
    )



def test_latest_repository_backlog_audit_finds_no_documented_package():
    """Only unchecked checklist entries may authorize another work package."""

    task_log = REPOSITORY_ROOT / "docs" / "open_tasks.md"
    active_tasks = task_log.read_text(encoding="utf-8")
    latest_package = active_tasks.split(
        "**Re-audit the documented backlog after the closed TinyCPU boundary**",
        maxsplit=1,
    )[1].split(
        "- [x] **Re-confirm the TinyCPU work-package boundary after electrical repair**",
        maxsplit=1,
    )[0]

    planning_files = (
        REPOSITORY_ROOT / relative_path
        for relative_path in subprocess.check_output(
            ["git", "ls-files", "*.md", "*.rst", "*.txt"],
            cwd=REPOSITORY_ROOT,
            text=True,
        ).splitlines()
    )
    unchecked_entries = []
    for planning_file in planning_files:
        for line_number, line in enumerate(
            planning_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if re.match(r"^\s*[-*] \[ \]", line):
                unchecked_entries.append(
                    f"{planning_file.relative_to(REPOSITORY_ROOT)}:{line_number}"
                )

    assert unchecked_entries == []
    assert "no unchecked work package is documented" in latest_package
    assert "all AP 1 through AP 15 packages remain\n    complete" in latest_package
    assert (
        "bounded, unchecked\n    package with explicit acceptance criteria"
        in latest_package
    )


def test_latest_tinycpu_request_preserves_the_closed_roadmap_boundary():
    """A request to execute work must not invent a successor to AP 15."""

    active_tasks = (REPOSITORY_ROOT / "docs" / "open_tasks.md").read_text(
        encoding="utf-8"
    )
    current_tasks = active_tasks.split("## Current tasks", maxsplit=1)[1]
    latest_package = current_tasks.split(
        "- [x] **Re-audit the documented backlog after the closed TinyCPU boundary**",
        maxsplit=1,
    )[0]
    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    expansion = (REPOSITORY_ROOT / "docs" / "expansion_roadmap.md").read_text(
        encoding="utf-8"
    )

    first_content_line = next(
        line for line in current_tasks.splitlines() if line.strip()
    )
    assert first_content_line == (
        "- [x] **Re-validate the TinyCPU backlog after the repository-wide audit**"
    )
    assert "AP 1 through AP 15 remain complete" in latest_package
    assert "no TinyCPU implementation package\n    to execute" in latest_package
    assert "no circuit, tooling, or release change is warranted" in latest_package
    assert "bounded, unchecked package with explicit acceptance criteria" in (
        latest_package
    )
    assert "ein weiteres\nRelease-Arbeitspaket ist derzeit nicht dokumentiert" in (
        detailed
    )
    assert "No successor package is\n  currently scoped" in expansion


def test_detailed_hardware_docs_do_not_advertise_completed_follow_ups():
    """Historical implementation notes must not look like active packages."""

    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    hardware_readme = (
        REPOSITORY_ROOT / "hardware" / "logisim" / "README.md"
    ).read_text(encoding="utf-8")

    assert "## Abgeschlossenes Folgepaket:" in detailed
    assert "## Folgepaket:" not in detailed

    stale_markers = (
        "The next integration step is",
        "The non-binary data paths are next",
        "Als nächster binärer\nOperationsschritt",
        "bleibt das folgende Arbeitspaket",
        "noch offen sind",
    )
    combined_docs = detailed + hardware_readme
    for marker in stale_markers:
        assert marker not in combined_docs


def test_bitwise_or_contract_records_completed_operations_integration():
    """The extracted OR box is already connected to the shared merge trees."""

    hardware_readme = (
        REPOSITORY_ROOT / "hardware" / "logisim" / "README.md"
    ).read_text(encoding="utf-8")
    or_contract = hardware_readme.split(
        "## Bitwise OR extraction contract", maxsplit=1
    )[1].split("## Bitwise XOR extraction contract", maxsplit=1)[0]

    assert "`Operations` instantiates\n`OrSubCircuit` exactly once" in or_contract
    assert "the integration package is complete" in or_contract
    assert (
        "Integration into\n`Operations` is a separate follow-up package"
        not in or_contract
    )


def test_datapath_control_notes_record_completed_integration():
    """The accumulator control boundary must not remain a future step."""

    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    combined_docs = detailed + template
    assert "`DecodeSignals.ACC_WRITE_REQUEST`-Grenze" in detailed
    assert "`DecodeSignals.ACC_WRITE_REQUEST`" in template
    assert "als nächstes folgen die Datenpfad-Steuernetze" not in combined_docs
    assert "Als Nächstes\nwerden Steuernetze" not in detailed


def test_address_and_memory_template_records_completed_integration():
    """Address selection and both RAM planes must not remain future wiring."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert "`EffectiveAddress.EFFECTIVE_ADDRESS`" in template
    assert "Daten- und Validitäts-RAM verwenden dieselben" in template
    assert "`DecodeSignals.ACC_MEMORY_REQUEST`" in template
    assert "Jedes Signal einzeln zeichnen und prüfen" not in template
    assert "Lesen und Schreiben getrennt testen" not in template
    assert "Splitter vermeiden, solange" not in template


def test_accumulator_data_template_records_operations_boundary():
    """Accumulator data selection must describe the extracted operations sheet."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert "`Operations.IMMEDIATE_VALUE`" in template
    assert "`Operations.MEMORY_VALUE`" in template
    assert "`Operations.ACC_VALUE`" in template
    assert "`Operations.RESULT_VALUE`" in template
    assert "`DecodeSignals.ACC_WRITE_REQUEST`" in template
    assert "`ACC_DATA_SELECT`" not in template
    assert "`ACC_NOT_SELECT`" not in template
    assert "`ACC_INPUT_SELECT`" not in template
    assert "`ACC_LOAD_REQUEST`" not in template


def test_status_template_records_operations_and_address_boundaries():
    """Status wiring must name the maintained producers and consumers."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert "`Operations.RESULT_IS_VALID`" in template
    assert "`Datapath.VALID_IN`" in template
    assert "`FetchDecode.NOT_ZERO`" in template
    assert "`Operations.OVERFLOW`" in template
    assert "`Operations.DIVIDE_BY_ZERO`" in template
    assert "`Operations.INVALID_OPERAND`" in template
    assert "`EffectiveAddress.ADDRESS_OUT_OF_RANGE`" in template
    assert "`AddressPath.OFFSET_CARRY`" in template
    assert "`FetchDecode`/Fehlerlogik" not in template


def test_error_template_records_sticky_register_boundary():
    """Error wiring must distinguish decoded and execution-derived causes."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert "`FetchDecodeControls.CLEAR_ERROR`" in template
    assert "`SET_ILL` und `SET_INPUT`" in template
    assert "vier abgeleiteten Ausführungsfehler" in template
    assert "set-dominanten Sticky-Register" in template
    for output in (
        "OVF_OUT", "DIV0_OUT", "ADDR_OUT", "INV_OUT", "ILL_OUT", "INPUT_OUT"
    ):
        assert f"`{output}`" in template
    assert "Sticky-Verhalten sowie Set-vor-Clear-Priorität prüfen" not in template


def test_halt_template_records_distinct_decode_and_trace_boundaries():
    """Halt documentation must name the maintained electrical event nets."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert "`FetchDecodeControls.HALT`" in template
    assert "`FetchDecodeControls.HALT_ERROR`" in template
    assert "Top-Level-Ausgang `HALTED`" in template
    assert "`HALTED_WITH_ERROR`" in template
    assert "`HALT_ENABLE` beziehungsweise" in template
    assert "`HALT_ERROR_ENABLE`" in template
    assert "kein zusätzliches `HALTED_STATE`-ODER" in template
    assert "normale und fehlerhafte Haltquelle" not in template


def test_top_level_template_is_a_completed_integration_reference():
    """The fully accepted wiring table must not read as an open build plan."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert template.startswith("# Referenz: TinyCPU-Top-Level-Integration")
    assert "kein offener Bauplan" in template
    assert "Alle Schritte 0 bis 11 sind abgeschlossen" in template
    assert "# Vorlage: TinyCPU-Übersichtsseite weiterbauen" not in template
    assert "Arbeitszettel für die manuelle Integration" not in template


def test_top_level_reference_requires_bounded_maintenance_changes():
    """Historical build checks must enforce the accepted maintenance gate."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert "Änderungsprotokoll für künftige Wartungspakete" in template
    assert "zuvor in `docs/open_tasks.md` abgegrenztes Wartungspaket" in template
    assert "darf weder `TinyCPU: INCOMPLETE`" in template
    assert "## Kopiervorlage für jeden Arbeitsschritt" not in template
    assert "Während des schrittweisen Aufbaus darf" not in template


def test_top_level_reference_describes_current_inspector_boundary():
    """The reference must distinguish connectivity diagnostics from acceptance."""

    template = (
        REPOSITORY_ROOT / "docs" / "tiny_cpu_top_level_template.md"
    ).read_text(encoding="utf-8")

    assert "`TinyCPUMain: connected`" in template
    assert "ersetzt weder\ndie fokussierten elektrischen Topologietests" in template
    assert "`connected` allein noch kein vollständiger elektrischer" in template
    assert "Inspector meldet die Top-Level-Blöcke bei solchen" not in template


def test_alu_architecture_note_matches_the_versioned_machine_contract():
    """The historical ALU sketch must not reopen an incompatible redesign."""

    note = (REPOSITORY_ROOT / "docs" / "tiny_cpu_alu_sketch.md").read_text(
        encoding="utf-8"
    )
    machine = json.loads(
        (REPOSITORY_ROOT / "hardware" / "logisim" / "tinycpu-machine-v1.json")
        .read_text(encoding="utf-8")
    )

    assert machine["word_bits"] == 22
    assert machine["opcode"]["bits"] == 6
    assert "Maschinenwort: 22 Bit" in note
    assert "Opcode: 6 Bit" in note
    assert "kein offenes\nFolgepaket" in note
    assert "## Nächster sinnvoller Schritt" not in note
    assert "auf 24-Bit-Instruktionen" not in note
