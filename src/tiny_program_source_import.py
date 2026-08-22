"""Fetch untrusted program sources into a non-executable quarantine.

This is deliberately only the acquisition boundary of the proposed import
pipeline.  A quarantined file must pass a separate security review before any
parser, transpiler, or runtime is allowed to consume it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_ALLOWED_HOSTS = frozenset({"raw.githubusercontent.com", "rosettacode.org"})
DEFAULT_MAX_BYTES = 256 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class QuarantineRecord:
    """Provenance recorded next to one byte-exact quarantined source."""

    source_url: str
    final_url: str
    byte_size: int
    sha256: str
    fetched_at: str
    status: str = "unreviewed"


def _validate_url(url: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("source URL must use HTTPS")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError("source URL must not contain credentials or a custom port")
    if parsed.hostname.casefold() not in allowed_hosts:
        raise ValueError(f"source host is not allowlisted: {parsed.hostname}")


def _quarantine_name(url: str) -> str:
    candidate = Path(urlparse(url).path).name or "source.txt"
    candidate = _SAFE_NAME.sub("_", candidate).strip("._") or "source.txt"
    return candidate[:120]


def fetch_to_quarantine(
    url: str,
    quarantine_dir: Path,
    *,
    allowed_hosts: frozenset[str] = DEFAULT_ALLOWED_HOSTS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    opener=urllib.request.urlopen,
) -> tuple[Path, Path]:
    """Download ``url`` once and atomically retain it with provenance metadata."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    _validate_url(url, allowed_hosts)
    request = urllib.request.Request(url, headers={"User-Agent": "TinyLanguage-source-import/1"})
    with opener(request, timeout=15) as response:
        final_url = response.geturl()
        _validate_url(final_url, allowed_hosts)
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f"source exceeds the {max_bytes}-byte quarantine limit")

    quarantine_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    stem = f"{digest[:16]}-{_quarantine_name(final_url)}"
    source_path = quarantine_dir / f"{stem}.quarantine"
    metadata_path = quarantine_dir / f"{stem}.json"
    record = QuarantineRecord(
        source_url=url,
        final_url=final_url,
        byte_size=len(payload),
        sha256=digest,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )

    for destination, content in (
        (source_path, payload),
        (metadata_path, (json.dumps(asdict(record), indent=2, sort_keys=True) + "\n").encode()),
    ):
        fd, temporary = tempfile.mkstemp(dir=quarantine_dir, prefix=".incoming-")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return source_path, metadata_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_url")
    parser.add_argument("--quarantine-dir", type=Path, default=Path("var/source-quarantine"))
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source, metadata = fetch_to_quarantine(
        args.source_url, args.quarantine_dir, max_bytes=args.max_bytes
    )
    print(f"quarantined source: {source}")
    print(f"provenance metadata: {metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
