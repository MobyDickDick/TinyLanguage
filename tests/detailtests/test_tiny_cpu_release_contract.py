import json
from pathlib import Path

import pytest

from tiny_cpu_release import (
    RELEASE_CONTRACT,
    ReleaseContractError,
    validate_release_contract,
)


REPOSITORY = Path(__file__).parents[2]


def _contract_repository(tmp_path: Path, mutate) -> Path:
    contract = json.loads((REPOSITORY / RELEASE_CONTRACT).read_text(encoding="utf-8"))
    mutate(contract)
    target = tmp_path / RELEASE_CONTRACT
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(contract), encoding="utf-8")
    for relative in (
        "hardware/logisim/tinycpu-16-12.json",
        "hardware/logisim/tinycpu-machine-v1.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPOSITORY / relative).read_bytes())
    for entry in contract.get("public_cli_entry_points", []):
        source = REPOSITORY / entry["path"]
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return tmp_path


def test_release_contract_cross_checks_sources_and_cli_help():
    checks = validate_release_contract(REPOSITORY)
    assert checks[-1] == "public CLI help"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.pop("hardware"), "hardware must be an object"),
        (
            lambda value: value["machine_format"].update(word_bits=21),
            "contradicts tinycpu-machine-v1.json",
        ),
        (
            lambda value: value["runtime"].update(logisim_evolution="latest"),
            "contradicts the pinned simulator constants",
        ),
        (
            lambda value: value["acceptance_report"].update(schema_version=1),
            "does not identify the AP-12 schema",
        ),
    ],
)
def test_release_contract_rejects_missing_or_contradictory_metadata(
    tmp_path, mutate, message
):
    repository = _contract_repository(tmp_path, mutate)
    with pytest.raises(ReleaseContractError, match=message):
        validate_release_contract(repository, check_cli_help=False)
