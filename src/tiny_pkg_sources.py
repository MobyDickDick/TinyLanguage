"""Bounded package transfers and staged, data-only archive installation.

Package sources are untrusted data. Only regular files and directories are
accepted; links, devices and archive metadata never become filesystem actions.
An existing installation survives every validation or transfer failure.
"""

from __future__ import annotations

import hashlib
import http.client
import gzip
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import tarfile
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener
import zlib

IO_TIMEOUT = 10.0
DOWNLOAD_DEADLINE = 60.0
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
MAX_EXTRACTED_BYTES = 256 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 10_000
CHUNK_BYTES = 64 * 1024


def normalize_checksum(value: str | None, *, required: bool = False) -> str | None:
    """Accept only a SHA-256 digest, optionally prefixed with ``sha256:``."""
    if value is None or value == "":
        if required:
            raise SystemExit("Remote packages require a SHA-256 checksum in tiny.lock; resolve again.")
        return None
    if not isinstance(value, str):
        raise SystemExit("Invalid SHA-256 checksum.")
    digest = value.strip().removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise SystemExit("Invalid SHA-256 checksum.")
    return digest.lower()


def checksum_matches(path: Path, checksum: str | None) -> bool:
    """Hash incrementally rather than loading a complete distribution into RAM."""
    digest = normalize_checksum(checksum)
    if digest is None:
        return True
    if path.stat().st_size > MAX_DOWNLOAD_BYTES:
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == digest


def _is_link(path: Path) -> bool:
    """Include Windows junctions where the host Python exposes them."""
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def check_destination(path: Path) -> None:
    """Reject link redirection in an existing destination or its ancestors."""
    for component in (path, *path.parents):
        if _is_link(component):
            raise SystemExit("Package destination contains a filesystem link.")


def validate_remote_url(url: str) -> None:
    """Allow HTTP(S) only, with no inline credentials or control characters."""
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                 and parsed.username is None and parsed.password is None
                 and not any(ord(char) < 33 or ord(char) == 127 for char in url))
        parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise SystemExit("Invalid package download URL; use HTTP(S) without inline credentials.")


def registry_cache_component(registry: str | None) -> str:
    """Preserve network host layouts and safely identify local registry files."""
    if not registry:
        return "registry"
    parsed = urlsplit(registry)
    if parsed.scheme in {"http", "https"}:
        validate_remote_url(registry)
        host = parsed.netloc.replace(":", "_")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", host) and not host.endswith("."):
            return host
    return "registry-" + hashlib.sha256(registry.encode("utf-8")).hexdigest()[:24]


class _PackageRedirects(HTTPRedirectHandler):
    """Validate redirect targets and prohibit an HTTPS downgrade."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_remote_url(newurl)
        if urlsplit(req.full_url).scheme == "https" and urlsplit(newurl).scheme != "https":
            raise SystemExit("Package download refused an HTTPS downgrade.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_to_cache(url: str, cache_path: Path, *, checksum: str | None) -> Path:
    """Verify a private temporary download before atomically updating the cache."""
    digest = normalize_checksum(checksum, required=True)
    validate_remote_url(url)
    check_destination(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        deadline = time.monotonic() + DOWNLOAD_DEADLINE
        opener = build_opener(_PackageRedirects())
        with opener.open(url, timeout=IO_TIMEOUT) as response:
            length = response.headers.get("Content-Length")
            expected = int(length) if length is not None else None
            if expected is not None and (expected < 0 or expected > MAX_DOWNLOAD_BYTES):
                raise SystemExit("Package download exceeds the size limit.")
            with tempfile.NamedTemporaryFile(dir=cache_path.parent, prefix=".download-", delete=False) as output:
                temporary = Path(output.name)
                count = 0
                hasher = hashlib.sha256()
                while True:
                    if time.monotonic() >= deadline:
                        raise SystemExit("Package download exceeded its time limit.")
                    # read1 returns after one underlying read, so a trickling
                    # peer cannot hide indefinitely inside a full-buffer read.
                    chunk = response.read1(CHUNK_BYTES)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > MAX_DOWNLOAD_BYTES:
                        raise SystemExit("Package download exceeds the size limit.")
                    hasher.update(chunk)
                    output.write(chunk)
            if expected is not None and count != expected:
                raise SystemExit("Package download was interrupted (incomplete body).")
            if hasher.hexdigest() != digest:
                raise SystemExit("Checksum mismatch for package download.")
        temporary.replace(cache_path)
        return cache_path
    except (OSError, URLError, http.client.HTTPException, ValueError):
        # Network exceptions can contain the complete URL or server text.
        raise SystemExit("Package download failed or timed out.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _member_path(name: str, dest: Path) -> Path:
    """Apply the same portable path contract on Windows and POSIX hosts."""
    parts = PurePosixPath(name).parts
    windows = PureWindowsPath(name)
    if (not parts or name.startswith("/") or windows.drive or "\\" in name
            or len(parts) > 64 or any(part == ".." for part in parts)):
        raise SystemExit("Refusing unsafe archive member path.")
    for part in parts:
        if (":" in part or part.endswith((".", " "))
                or any(ord(char) < 32 or char in '<>"|?*' for char in part)
                or part.split(".")[0].upper() in {
                    "CON", "PRN", "AUX", "NUL",
                    *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
                }):
            raise SystemExit("Refusing nonportable archive member path.")
    target = dest.joinpath(*parts)
    if not target.resolve().is_relative_to(dest.resolve()):
        raise SystemExit("Refusing unsafe archive member path.")
    return target


def safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract bounded regular data without restoring ownership or permissions."""
    check_destination(dest)
    total = 0
    seen: dict[str, bool] = {}
    spellings: dict[str, str] = {}
    for count, member in enumerate(tar, start=1):
        if count > MAX_MEMBERS:
            raise SystemExit("Package archive has too many members.")
        if not (member.isfile() or member.isdir()) or member.issparse():
            raise SystemExit("Package archives may contain only regular files and directories.")
        if member.size < 0 or member.size > MAX_FILE_BYTES:
            raise SystemExit("Package archive member exceeds the size limit.")
        total += member.size
        if total > MAX_EXTRACTED_BYTES:
            raise SystemExit("Package archive exceeds the expanded size limit.")
        # Conventional tarballs may contain an entry for the root directory.
        if member.name in {".", "./"} and member.isdir():
            continue
        target = _member_path(member.name, dest)
        relative = target.relative_to(dest)
        for part in (relative, *relative.parents):
            spelling = part.as_posix()
            folded = spelling.casefold()
            if folded in spellings and spellings[folded] != spelling:
                raise SystemExit("Package archive contains conflicting member paths.")
            spellings[folded] = spelling
        key = target.relative_to(dest).as_posix().casefold()
        if key in seen or any(seen.get(parent.as_posix().casefold()) is False
                              for parent in target.relative_to(dest).parents if parent != Path(".")):
            raise SystemExit("Package archive contains conflicting member paths.")
        seen[key] = member.isdir()
        check_destination(target)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, CHUNK_BYTES)


class _BoundedTarReader:
    """Bound all decompressed bytes, including tar/PAX headers and padding."""

    def __init__(self, source):
        self.source = source
        self.remaining = MAX_EXTRACTED_BYTES + MAX_MEMBERS * 1024

    def read(self, size):
        data = self.source.read(min(size, self.remaining + 1))
        self.remaining -= len(data)
        if self.remaining < 0:
            raise SystemExit("Package archive exceeds the decompressed stream limit.")
        return data


def _install_staged(stage: Path, dest: Path, *, force: bool) -> None:
    """Keep the previous directory available until the replacement is ready."""
    check_destination(dest)
    if not dest.exists():
        stage.rename(dest)
        return
    if not force:
        raise SystemExit(f"Destination already exists: {dest}")
    backup = Path(tempfile.mkdtemp(dir=dest.parent, prefix=".previous-"))
    previous = backup / "package"
    preserve_backup = False
    try:
        dest.rename(previous)
        try:
            stage.rename(dest)
        except BaseException:
            try:
                previous.rename(dest)
            except OSError:
                preserve_backup = True
                raise SystemExit(f"Package replacement failed; previous installation retained at {previous}") from None
            raise
    finally:
        if not preserve_backup:
            shutil.rmtree(backup)


def copy_tree(source: Path, dest: Path, *, force: bool) -> None:
    """Stage local sources too; do not follow source-tree links."""
    check_destination(source)
    check_destination(dest)
    if dest.resolve().is_relative_to(source.resolve()):
        raise SystemExit("Package destination must be outside its source tree.")
    if dest.exists() and not force:
        raise SystemExit(f"Destination already exists: {dest}")
    ignore = shutil.ignore_patterns(".git", "__pycache__", ".tiny-cache", "build", ".venv")

    def safe_ignore(directory, names):
        ignored = ignore(directory, names)
        for name in set(names) - set(ignored):
            path = Path(directory) / name
            if _is_link(path) or not (path.is_dir() or path.is_file()):
                raise SystemExit("Local package sources may contain only regular files and directories.")
        return ignored

    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent, prefix=".install-") as temporary:
        stage = Path(temporary) / "package"
        shutil.copytree(source, stage, ignore=safe_ignore)
        _install_staged(stage, dest, force=force)


def vendor_from_dist(dist: str, dest: Path, *, force: bool,
                     cache_path: Path | None = None, checksum: str | None = None) -> None:
    """Validate and stage a distribution before replacing its vendor directory."""
    check_destination(dest)
    if dest.exists() and not force:
        raise SystemExit(f"Destination already exists: {dest}")
    remote = urlsplit(dist).scheme.lower() in {"http", "https"}
    normalize_checksum(checksum, required=remote)
    if remote:
        if cache_path is None:
            raise SystemExit("Cache path required for remote registry fetches.")
        validate_remote_url(dist)
        check_destination(cache_path)
        if cache_path.is_file() and checksum_matches(cache_path, checksum):
            dist_path = cache_path
        else:
            dist_path = download_to_cache(dist, cache_path, checksum=checksum)
    else:
        dist_path = Path(dist.removeprefix("file://"))
    try:
        if not remote and dist_path.is_dir():
            if checksum is not None:
                raise SystemExit("Directory distributions cannot use an archive checksum; use a path dependency.")
            copy_tree(dist_path, dest, force=force)
            return
        if dist_path.stat().st_size > MAX_DOWNLOAD_BYTES:
            raise SystemExit("Package archive exceeds the size limit.")
        if not checksum_matches(dist_path, checksum):
            raise SystemExit("Checksum mismatch for package archive.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent, prefix=".install-") as temporary:
            stage = Path(temporary) / "package"
            stage.mkdir()
            with gzip.open(dist_path, "rb") as data:
                bounded = _BoundedTarReader(data)
                with tarfile.open(fileobj=bounded, mode="r|") as archive:
                    safe_extract(archive, stage)
                # tar stops at its end marker; consume the remaining gzip
                # stream too so missing footers and CRC failures are rejected.
                while bounded.read(CHUNK_BYTES):
                    pass
            _install_staged(stage, dest, force=force)
    except (tarfile.TarError, OSError, EOFError, ValueError, zlib.error):
        raise SystemExit("Package archive is malformed, unsupported, or inaccessible.") from None
