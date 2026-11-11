"""Adversarial distributions must never replace an accepted installation."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tarfile
import threading
import time

import pytest

import tiny_pkg_sources as sources
from tiny_pkg_cli import _vendor_dependency, main as pkg_main
from tiny_pkg_resolution import write_lockfile


def archive_bytes(entries):
    """Build untrusted tar fixtures without ever extracting them in the test."""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, value in entries:
            member = tarfile.TarInfo(name)
            if isinstance(value, bytes):
                member.size = len(value)
                archive.addfile(member, io.BytesIO(value))
            else:
                member.type = value[1]
                member.linkname = "../escaped"
                archive.addfile(member)
    return output.getvalue()


@contextmanager
def http_distribution(body, *, declared_length=None, delay=0, trickle=False, redirect=None):
    """A loopback server exercises actual urllib reads and timeout handling."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(302 if redirect else 200)
            if redirect:
                self.send_header("Location", redirect)
            if declared_length is not None:
                self.send_header("Content-Length", str(declared_length))
            self.end_headers()
            try:
                if trickle:
                    for byte in body:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(delay)
                else:
                    time.sleep(delay)
                    self.wfile.write(body)
            except (OSError, ConnectionError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/package.tar.gz", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_verified_download_and_offline_cache(tmp_path):
    body = archive_bytes([("src/main.tiny", b"print(7);"), ("empty", ("type", tarfile.DIRTYPE))])
    checksum = hashlib.sha256(body).hexdigest()
    cache = tmp_path / "cache/package.tar.gz"
    with http_distribution(body, declared_length=len(body)) as (url, requests):
        for version in ("one", "two"):
            sources.vendor_from_dist(url, tmp_path / version, force=False, cache_path=cache,
                                     checksum="sha256:" + checksum.upper())
        assert len(requests) == 1
    sources.vendor_from_dist(url, tmp_path / "offline", force=False, cache_path=cache, checksum=checksum)
    assert (tmp_path / "offline/src/main.tiny").read_bytes() == b"print(7);"
    assert (tmp_path / "offline/empty").is_dir()


@pytest.mark.parametrize("checksum", [None, "", "sha256:", "wrong", "g" * 64, 12])
def test_remote_requires_valid_checksum_before_network(tmp_path, checksum):
    with pytest.raises(SystemExit, match="checksum"):
        sources.vendor_from_dist("http://127.0.0.1:1/never", tmp_path / "dest", force=False,
                                 cache_path=tmp_path / "cache", checksum=checksum)
    assert not (tmp_path / "dest").exists()
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("failure", ["checksum", "interrupted", "length", "stream", "stall", "trickle"])
def test_failed_transfer_keeps_cache_and_installation(tmp_path, monkeypatch, failure):
    body = b"a" * 200
    cache = tmp_path / "package.tar.gz"
    cache.write_bytes(b"previous cache")
    dest = tmp_path / "installed"
    dest.mkdir()
    (dest / "keep").write_text("accepted")
    checksum = hashlib.sha256(body).hexdigest() if failure != "checksum" else "0" * 64
    monkeypatch.setattr(sources, "MAX_DOWNLOAD_BYTES", 100 if failure in {"length", "stream"} else 1000)
    monkeypatch.setattr(sources, "IO_TIMEOUT", 0.05 if failure == "stall" else 1)
    monkeypatch.setattr(sources, "DOWNLOAD_DEADLINE", 0.06 if failure == "trickle" else 5)
    declared = 300 if failure == "interrupted" else (200 if failure == "length" else None)
    with http_distribution(body, declared_length=declared, delay=0.2 if failure == "stall" else 0.01,
                           trickle=failure == "trickle") as (url, requests):
        started = time.monotonic()
        expected_error = {"checksum": "Checksum mismatch", "interrupted": "interrupted",
                          "length": "size limit", "stream": "size limit",
                          "stall": "timed out", "trickle": "time limit"}[failure]
        with pytest.raises(SystemExit, match=expected_error):
            sources.vendor_from_dist(url, dest, force=True, cache_path=cache, checksum=checksum)
        assert time.monotonic() - started < 3
        assert len(requests) == 1
    assert cache.read_bytes() == b"previous cache"
    assert (dest / "keep").read_text() == "accepted"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["installed", "package.tar.gz"]


@pytest.mark.parametrize("name", ["../installed-sibling/escape", "/absolute", "C:/escape",
                                 "C:escape", "a/../../escape", "a\\..\\escape", "//server/share",
                                 "file:stream", "NUL.txt", "a./file", "a /file"])
def test_archive_paths_are_portable_and_contained(tmp_path, name):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(archive_bytes([("ordinary", b"first"), (name, b"escape")]))
    dest = tmp_path / "installed"
    dest.mkdir()
    (dest / "keep").write_text("accepted")
    with pytest.raises(SystemExit):
        sources.vendor_from_dist(str(archive), dest, force=True)
    assert (dest / "keep").read_text() == "accepted"
    assert not (dest / "ordinary").exists()
    assert {path.name for path in tmp_path.iterdir()} == {"bad.tar.gz", "installed"}


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE,
                                 tarfile.CHRTYPE, tarfile.BLKTYPE])
def test_archive_rejects_links_and_special_files(tmp_path, kind):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(archive_bytes([("link", ("type", kind)), ("link/file", b"escape")]))
    with pytest.raises(SystemExit, match="regular files"):
        sources.vendor_from_dist(str(archive), tmp_path / "dest", force=False)
    assert not (tmp_path / "dest").exists()
    assert not list(tmp_path.glob(".install-*"))


@pytest.mark.parametrize("entries", [[("a", b"1"), ("a", b"2")],
                                     [("A/file", b"1"), ("a/other", b"2")],
                                     [("a", b"1"), ("a/child", b"2")]])
def test_archive_rejects_conflicting_paths(tmp_path, entries):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(archive_bytes(entries))
    with pytest.raises(SystemExit, match="conflicting"):
        sources.vendor_from_dist(str(archive), tmp_path / "dest", force=False)


@pytest.mark.parametrize("limit", ["MAX_FILE_BYTES", "MAX_EXTRACTED_BYTES", "MAX_MEMBERS"])
def test_archive_resource_limits(tmp_path, monkeypatch, limit):
    archive = tmp_path / "big.tar.gz"
    archive.write_bytes(archive_bytes([("one", b"1234"), ("two", b"5678")]))
    monkeypatch.setattr(sources, limit, 1 if limit == "MAX_MEMBERS" else 6 if limit == "MAX_EXTRACTED_BYTES" else 3)
    with pytest.raises(SystemExit, match="limit|too many"):
        sources.vendor_from_dist(str(archive), tmp_path / "dest", force=False)
    assert not (tmp_path / "dest").exists()


def test_decompressed_header_budget(tmp_path, monkeypatch):
    archive = tmp_path / "headers.tar.gz"
    archive.write_bytes(archive_bytes([("x" * 3000, b"x")]))
    monkeypatch.setattr(sources, "MAX_EXTRACTED_BYTES", 1)
    monkeypatch.setattr(sources, "MAX_MEMBERS", 1)
    with pytest.raises(SystemExit, match="decompressed stream"):
        sources.vendor_from_dist(str(archive), tmp_path / "dest", force=False)


@pytest.mark.parametrize("body", [b"not gzip", b"\x1f\x8b\x08", archive_bytes([("ok", b"x")])[:30],
                                  archive_bytes([("ok", b"x")])[:-8]])
def test_malformed_archive_leaves_no_installation(tmp_path, body):
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(body)
    with pytest.raises(SystemExit, match="malformed"):
        sources.vendor_from_dist(str(archive), tmp_path / "dest", force=False)
    assert not (tmp_path / "dest").exists()


def test_force_replacement_and_rollback(tmp_path, monkeypatch):
    archive = tmp_path / "good.tar.gz"
    archive.write_bytes(archive_bytes([("new", b"new")]))
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "old").write_text("old")
    rename = Path.rename

    def fail_install(path, target):
        if path.name == "package" and path.parent.name.startswith(".install-"):
            raise OSError("simulated disk failure")
        return rename(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_install)
        with pytest.raises(SystemExit):
            sources.vendor_from_dist(str(archive), dest, force=True)
    assert (dest / "old").read_text() == "old"
    sources.vendor_from_dist(str(archive), dest, force=True)
    assert list(dest.iterdir()) == [dest / "new"]
    assert not list(tmp_path.glob(".previous-*"))


def test_failed_rollback_preserves_previous_installation(tmp_path, monkeypatch):
    archive = tmp_path / "good.tar.gz"
    archive.write_bytes(archive_bytes([("new", b"new")]))
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "old").write_text("accepted")
    rename = Path.rename

    def fail_after_backup(path, target):
        if path.name == "package":
            raise OSError("simulated replacement and rollback failure")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_after_backup)
    with pytest.raises(SystemExit, match="previous installation retained"):
        sources.vendor_from_dist(str(archive), dest, force=True)
    backups = list(tmp_path.glob(".previous-*/package/old"))
    assert len(backups) == 1
    assert backups[0].read_text() == "accepted"


@pytest.mark.parametrize("registry", ["registry.json", "file://C:/registry/index.json",
                                    "/registry/index.json", "https://[::1]:1234"])
def test_registry_cache_path_is_one_component_and_shared(registry):
    from tiny_language_module_resolution import _registry_host

    host = sources.registry_cache_component(registry)
    assert host == _registry_host(registry)
    assert "/" not in host and "\\" not in host and ":" not in host


def test_remote_registry_cannot_substitute_an_unlocked_digest(tmp_path):
    index = {"dep": {"1.0.0": {"dist": "http://127.0.0.1:1/never", "sha256": "0" * 64}}}
    (tmp_path / "tiny_registry.json").write_text(json.dumps(index))
    # The old checksum field could contain a hash of 'name@version', not an
    # archive hash. It cannot stand in for a missing registry_checksum.
    entry = {"name": "dep", "version": "1.0.0", "source": "registry", "checksum": "0" * 64}
    with pytest.raises(SystemExit, match="checksum in tiny.lock"):
        _vendor_dependency(entry, tmp_path, tmp_path / "vendor", cache_root=tmp_path / "cache", force=False)
    assert not (tmp_path / "vendor").exists()


@pytest.mark.parametrize("url", ["http://user:secret@host/file?token=secret",
                                "http://host/\nsecret", "http://[invalid", "ftp://host/file"])
def test_urls_and_diagnostics_do_not_expose_credentials(tmp_path, url):
    with pytest.raises(SystemExit) as error:
        sources.download_to_cache(url, tmp_path / "cache", checksum="0" * 64)
    assert "secret" not in str(error.value)


def test_http_error_diagnostics_do_not_echo_url_secrets(tmp_path):
    with http_distribution(b"", redirect="/loop?token=secret") as (url, _):
        with pytest.raises(SystemExit) as error:
            sources.download_to_cache(url + "?token=secret", tmp_path / "cache", checksum="0" * 64)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("field,value", [("name", "../escape"), ("version", "../escape"),
                                        ("name", "NUL"), ("name", "C:escape")])
def test_lockfile_components_cannot_escape_vendor(tmp_path, field, value):
    entry = {"name": "dep", "version": "1.0.0", "source": "path", "path": "source", field: value}
    with pytest.raises(SystemExit, match="component"):
        _vendor_dependency(entry, tmp_path, tmp_path / "vendor", cache_root=tmp_path / "cache", force=True)


def test_registry_digest_is_locked_and_metadata_changes_are_rejected(tmp_path, monkeypatch):
    body = archive_bytes([("src/dep.tiny", b"fn value() { return 7; }")])
    digest = hashlib.sha256(body).hexdigest()
    manifest = tmp_path / "tiny.toml"
    manifest.write_text('[package]\nname="app"\nversion="1.0.0"\n[dependencies]\ndep="1.0.0"\n'
                        '[registries]\ndefault="https://registry.example.com"\n')
    index = tmp_path / "tiny_registry.json"
    with http_distribution(body) as (url, requests):
        def metadata(checksum):
            return {"dep": {"1.0.0": {"dist": url, "sha256": checksum}}}
        index.write_text(json.dumps(metadata(digest)))
        # Resolution must use the manifest's index even from an unrelated cwd.
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        write_lockfile(tmp_path / "tiny.lock", manifest)
        assert f'registry_checksum = "{digest}"' in (tmp_path / "tiny.lock").read_text()
        assert pkg_main(["vendor", "--manifest", str(manifest)]) == 0
        assert len(requests) == 1
        index.write_text(json.dumps(metadata("0" * 64)))
        with pytest.raises(SystemExit, match="differs from tiny.lock"):
            pkg_main(["vendor", "--manifest", str(manifest), "--force"])
        assert len(requests) == 1


def test_links_in_source_or_destination_are_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    link = source / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not grant symlink creation privileges")
    with pytest.raises(SystemExit, match="regular files"):
        sources.copy_tree(source, tmp_path / "dest", force=False)
    with pytest.raises(SystemExit, match="filesystem link"):
        sources.copy_tree(outside, link / "dest", force=True)
    assert not list(outside.iterdir())
