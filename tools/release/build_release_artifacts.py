#!/usr/bin/env python3
"""Build deterministic release artifacts and generate SBOM + signatures."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def read_version() -> str:
    return Path("VERSION").read_text(encoding="utf-8").strip()


def git_tag() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match"], text=True
        ).strip()
    except subprocess.CalledProcessError:
        return None


def git_dirty() -> bool:
    status = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    return bool(status.strip())


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_timestamp(epoch: int) -> str:
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_spdx(artifacts: list[dict[str, str]], version: str, commit: str,
                  *, epoch: int = 315532800, dependencies: list[dict] | None = None) -> dict:
    created = build_timestamp(epoch)
    namespace = f"https://tinylanguage.org/spdx/{version}/{commit}"
    packages = []
    relationships = []

    for idx, artifact in enumerate(artifacts, start=1):
        spdx_id = f"SPDXRef-Artifact-{idx}"
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": artifact["name"],
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "checksums": [
                    {
                        "algorithm": "SHA256",
                        "checksumValue": artifact["sha256"],
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": spdx_id,
            }
        )

    for idx, dependency in enumerate(dependencies or [], start=1):
        packages.append({
            "SPDXID": f"SPDXRef-BuildDependency-{idx}",
            "name": dependency["name"], "versionInfo": dependency["version"],
            "downloadLocation": "NOASSERTION", "filesAnalyzed": False,
            "primaryPackagePurpose": "LIBRARY",
        })
        relationships.append({
            "spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES",
            "relatedSpdxElement": f"SPDXRef-BuildDependency-{idx}",
        })

    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "name": f"TinyLanguage {version} release SBOM",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": created,
            "creators": ["Tool: tools/release/build_release_artifacts.py"],
        },
        "packages": packages,
        "relationships": relationships,
    }


def sign_files(files: list[Path], gpg_key_id: str | None) -> list[str]:
    gpg = shutil.which("gpg")
    if not gpg:
        raise RuntimeError("gpg is required for --sign but was not found on PATH")
    signatures = []
    for file_path in files:
        cmd = [
            gpg,
            "--batch",
            "--yes",
            "--armor",
            "--detach-sign",
        ]
        if gpg_key_id:
            cmd.extend(["--local-user", gpg_key_id])
        cmd.append(str(file_path))
        run(cmd)
        signatures.append(f"{file_path.name}.asc")
    return signatures


def build_source_archive(output_dir: Path, tag: str | None, version: str) -> Path:
    archive_name = f"TinyLanguage-v{version}.tar.gz"
    archive_path = output_dir / archive_name
    ref = tag or "HEAD"
    run(["git", "archive", "--format=tar.gz", "-o", str(archive_path), ref])
    return archive_path


def normalize_vsix(path: Path, epoch: int) -> None:
    """Remove host timestamps, permissions and ZIP entry ordering from VSIX."""
    timestamp = dt.datetime.fromtimestamp(max(epoch, 315532800), tz=dt.timezone.utc)
    date_time = timestamp.timetuple()[:6]
    with zipfile.ZipFile(path) as archive:
        entries = [(entry.filename, archive.read(entry)) for entry in archive.infolist()]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries):
            entry = zipfile.ZipInfo(name, date_time=date_time)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)


def build_from_archive(source: Path, destination: Path, *, python: bool,
                       binary: bool, vsix: bool, epoch: int) -> list[Path]:
    """Build only from archived sources; never mix working-tree and tag inputs."""
    with tempfile.TemporaryDirectory(prefix="tiny-build-", dir=destination.parent) as directory:
        root = Path(directory)
        with tarfile.open(source) as archive:
            archive.extractall(root, filter="data")
        environment = {**os.environ, "SOURCE_DATE_EPOCH": str(epoch), "PYTHONHASHSEED": "0"}
        destination.mkdir(parents=True, exist_ok=True)
        if python:
            for hook in ("build_sdist", "build_wheel"):
                subprocess.run([sys.executable, "-c",
                                "import sys; output = sys.argv[1]; sys.path.insert(0, 'tools'); "
                                "import packaging_backend as b; " + f"b.{hook}(output)",
                                str(destination)], cwd=root, env=environment, check=True)
            if not list(destination.glob("*.whl")) or not list(destination.glob("tinylanguage-*.tar.gz")):
                raise RuntimeError("Python build did not produce both a wheel and an sdist")
        if binary:
            subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
                            "--distpath", str(destination), "tools/release/tinylanguage.spec"],
                           cwd=root, env=environment, check=True)
            system = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}[platform.system()]
            machine = {"AMD64": "x86_64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())
            suffix = ".exe" if system == "windows" else ""
            (destination / f"tiny-language{suffix}").rename(
                destination / f"tiny-language-{system}-{machine}{suffix}")
        if vsix:
            npm = shutil.which("npm")
            if not npm:
                raise RuntimeError("npm is required for --vsix")
            extension = root / "vscode-extension"
            subprocess.run([npm, "ci"], cwd=extension, env=environment, check=True)
            path = destination / "tiny-language-vscode.vsix"
            subprocess.run([npm, "exec", "--no", "--", "vsce", "package", "--out", str(path)],
                           cwd=extension, env=environment, check=True)
            normalize_vsix(path, epoch)
    return sorted(path for path in destination.iterdir() if path.is_file())


def verify_signatures(files: list[Path]) -> None:
    for path in files:
        run(["gpg", "--batch", "--verify", str(path) + ".asc", str(path)])


def build_release(args: argparse.Namespace) -> int:
    version = args.version or read_version()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tag = args.tag or git_tag()
    ref = tag or "HEAD"
    commit = subprocess.check_output(["git", "rev-parse", f"{ref}^{{commit}}"], text=True).strip()
    epoch = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", commit], text=True).strip())

    if tag and tag != f"v{version}":
        raise RuntimeError(
            f"Git tag {tag} does not match VERSION v{version}. Update VERSION or use --tag."
        )

    source_archive = build_source_archive(output_dir, tag, version)
    with tarfile.open(source_archive) as archive:
        archived_version = archive.extractfile("VERSION").read().decode("utf-8").strip()
        extension_manifest = archive.extractfile("vscode-extension/package.json")
        extension_version = json.load(extension_manifest)["version"]
        extension_lock = json.load(archive.extractfile("vscode-extension/package-lock.json"))
    if archived_version != version:
        raise RuntimeError(f"Archived VERSION {archived_version} does not match {version}")
    python_build = getattr(args, "python", False)
    binary_build = getattr(args, "binary", False)
    vsix_build = getattr(args, "vsix", False)
    if vsix_build and (extension_version != version or extension_lock["version"] != version
                       or extension_lock["packages"][""]["version"] != version):
        raise RuntimeError("VS Code manifest/lock versions must match the release VERSION")
    paths = [source_archive]
    dependencies = []
    reproduced_artifacts = []
    tool_versions = {"python": platform.python_version()}
    if python_build or binary_build or vsix_build:
        with tempfile.TemporaryDirectory(prefix="tiny-artifacts-", dir=output_dir.parent) as directory:
            first = Path(directory) / "first"
            built = build_from_archive(source_archive, first, python=python_build,
                                       binary=binary_build, vsix=vsix_build, epoch=epoch)
            if getattr(args, "verify_reproducible", False):
                second = build_from_archive(source_archive, Path(directory) / "second",
                                            python=python_build, binary=binary_build,
                                            vsix=vsix_build, epoch=epoch)
                if {p.name: sha256sum(p) for p in built} != {p.name: sha256sum(p) for p in second}:
                    raise RuntimeError("Rebuild hashes differ; release cannot be signed off")
                reproduced_artifacts = [path.name for path in built]
            for path in built:
                target = output_dir / path.name
                shutil.copyfile(path, target)
                paths.append(target)
        dependencies = sorted(
            [{"name": d.metadata["Name"], "version": d.version}
             for d in importlib.metadata.distributions()], key=lambda item: item["name"].lower())
        if vsix_build:
            tool_versions["node"] = subprocess.check_output(["node", "--version"], text=True).strip()
            tool_versions["npm"] = subprocess.check_output([shutil.which("npm"), "--version"], text=True).strip()
            dependencies += [{"name": "npm:" + name.removeprefix("node_modules/"),
                              "version": package["version"],
                              "integrity": package.get("integrity")}
                             for name, package in sorted(extension_lock["packages"].items()) if name]
    for extra in getattr(args, "include_artifact", []):
        path = Path(extra).resolve()
        reserved = {"SHA256SUMS", "build-info.json", f"TinyLanguage-v{version}-sbom.spdx.json"}
        if path.name in {p.name for p in paths} or path.name in reserved:
            raise RuntimeError(f"Duplicate or reserved artifact name: {path.name}")
        target = output_dir / path.name
        if path != target:
            shutil.copyfile(path, target)
        paths.append(target)
    artifacts = [{"name": p.name, "sha256": sha256sum(p), "size": str(p.stat().st_size)}
                 for p in sorted(paths)]

    sbom_path = output_dir / f"TinyLanguage-v{version}-sbom.spdx.json"
    sbom_payload = generate_spdx(artifacts, version, commit, epoch=epoch, dependencies=dependencies)
    sbom_path.write_text(json.dumps(sbom_payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    artifacts.append(
        {
            "name": sbom_path.name,
            "sha256": sha256sum(sbom_path),
            "size": str(sbom_path.stat().st_size),
        }
    )

    checksums_path = output_dir / "SHA256SUMS"
    with checksums_path.open("w", encoding="utf-8", newline="\n") as handle:
        for artifact in artifacts:
            handle.write(f"{artifact['sha256']}  {artifact['name']}\n")

    build_info = {
        "version": version,
        "git": {
            "commit": commit,
            "tag": tag,
            "working_tree_dirty": git_dirty(),
            "source": "git archive (working-tree edits excluded)",
        },
        "build": {
            "source_date_epoch": epoch,
            "timestamp_utc": dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_timestamp_utc": build_timestamp(epoch),
            "platform": platform.platform(),
            "python": sys.version.replace("\n", " "),
            "builder_image": os.environ.get("BUILDER_IMAGE_DIGEST"),
            "builder_script_sha256": sha256sum(Path(__file__)),
            "dependencies": dependencies,
            "tools": tool_versions,
            "runtime_dependencies": [],
            "reproduced_artifacts": reproduced_artifacts,
            "supplied_artifacts": [Path(p).name for p in getattr(args, "include_artifact", [])],
            "reproducibility_verified": bool(getattr(args, "verify_reproducible", False)
                                              and (python_build or binary_build or vsix_build)
                                              and not getattr(args, "include_artifact", [])),
        },
        "artifacts": artifacts,
    }

    signature_files: list[str] = []
    if args.sign:
        signature_files = sign_files(
            [output_dir / a["name"] for a in artifacts] + [checksums_path],
            args.gpg_key_id,
        )
        build_info["signatures"] = signature_files
        build_info["signing"] = {
            "gpg_key_id": args.gpg_key_id,
        }
        verify_signatures([output_dir / a["name"] for a in artifacts] + [checksums_path])
        build_info["signatures"].append("build-info.json.asc")

    build_info_path = output_dir / "build-info.json"
    build_info_path.write_text(
        json.dumps(build_info, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if args.sign:
        sign_files([build_info_path], args.gpg_key_id)
        verify_signatures([build_info_path])

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build TinyLanguage release artifacts, SBOMs, and signatures."
    )
    parser.add_argument(
        "--output-dir",
        default="dist/release",
        help="Output directory for artifacts and metadata.",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Override VERSION when building release artifacts.",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Git tag to archive (defaults to exact-match tag or HEAD).",
    )
    parser.add_argument(
        "--sign",
        action="store_true",
        help="Sign artifacts and SHA256SUMS using gpg.",
    )
    parser.add_argument("--python", action="store_true", help="Build wheel and installable sdist from archived sources")
    parser.add_argument("--binary", action="store_true", help="Build the host-platform standalone interpreter")
    parser.add_argument("--vsix", action="store_true", help="Build the locked VS Code extension")
    parser.add_argument("--verify-reproducible", action="store_true", help="Build selected artifacts twice and compare hashes")
    parser.add_argument("--include-artifact", action="append", default=[], help="Include an existing platform artifact in checksums, SBOM and signatures")
    parser.add_argument(
        "--gpg-key-id",
        default=os.environ.get("GPG_KEY_ID"),
        help="GPG key id/email for signing (or set GPG_KEY_ID).",
    )

    args = parser.parse_args()
    return build_release(args)


if __name__ == "__main__":
    raise SystemExit(main())
