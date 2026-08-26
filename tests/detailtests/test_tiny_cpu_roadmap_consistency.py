"""Keep the high-level TinyCPU roadmap aligned with its acceptance checklist."""

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[2]


def test_expansion_roadmap_does_not_reopen_completed_electrical_packages():
    """A completed AP must not remain advertised as the next work package."""

    detailed = (REPOSITORY_ROOT / "docs" / "tiny_cpu_roadmap.md").read_text(
        encoding="utf-8"
    )
    expansion = (REPOSITORY_ROOT / "docs" / "expansion_roadmap.md").read_text(
        encoding="utf-8"
    )

    for package in range(9, 13):
        assert re.search(rf"^- \[x\] \*\*AP {package}:\*\*", detailed, re.MULTILINE)

    tinycpu_section = expansion.split("## 1) Native compiler", maxsplit=1)[0]
    assert "**Completed boundary**: AP 9 through AP 12" in tinycpu_section
    assert "**Next package**: none is currently scoped" in tinycpu_section
    assert "add a mandatory headless" not in tinycpu_section


def test_active_backlog_agrees_that_no_tinycpu_package_is_scoped():
    """Do not claim an empty roadmap while retaining an unchecked CPU task."""

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
    assert "**Next package**: none is currently scoped" in tinycpu_section
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
