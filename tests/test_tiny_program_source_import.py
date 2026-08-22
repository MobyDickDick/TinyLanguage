import hashlib
import json
from pathlib import Path

import pytest

from tiny_program_source_import import fetch_to_quarantine


class FakeResponse:
    def __init__(self, payload: bytes, final_url: str):
        self.payload = payload
        self.final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def geturl(self):
        return self.final_url

    def read(self, limit: int):
        return self.payload[:limit]


def opener(payload: bytes, final_url: str):
    def open_request(request, timeout):
        assert request.full_url.startswith("https://")
        assert timeout == 15
        return FakeResponse(payload, final_url)

    return open_request


def test_fetch_retains_byte_exact_source_and_provenance(tmp_path: Path):
    payload = b"print('untrusted')\n"
    url = "https://raw.githubusercontent.com/example/project/main/demo.py"

    source, metadata = fetch_to_quarantine(
        url, tmp_path / "quarantine", opener=opener(payload, url)
    )

    assert source.read_bytes() == payload
    record = json.loads(metadata.read_text())
    assert record["source_url"] == url
    assert record["final_url"] == url
    assert record["status"] == "unreviewed"
    assert record["byte_size"] == len(payload)
    assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    assert source.suffix == ".quarantine"
    assert source.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "url",
    [
        "http://rosettacode.org/wiki/Hello_world",
        "https://evil.example/program.py",
        "https://user:secret@rosettacode.org/program.py",
        "https://rosettacode.org:444/program.py",
    ],
)
def test_fetch_rejects_unsafe_source_urls(tmp_path: Path, url: str):
    with pytest.raises(ValueError):
        fetch_to_quarantine(url, tmp_path, opener=opener(b"", url))


def test_fetch_rejects_redirect_to_non_allowlisted_host(tmp_path: Path):
    url = "https://rosettacode.org/wiki/Demo"
    with pytest.raises(ValueError, match="not allowlisted"):
        fetch_to_quarantine(
            url,
            tmp_path,
            opener=opener(b"payload", "https://evil.example/payload"),
        )


def test_fetch_rejects_oversized_source_without_writing(tmp_path: Path):
    url = "https://rosettacode.org/wiki/Demo"
    with pytest.raises(ValueError, match="exceeds"):
        fetch_to_quarantine(url, tmp_path, max_bytes=4, opener=opener(b"12345", url))
    assert not list(tmp_path.iterdir())
