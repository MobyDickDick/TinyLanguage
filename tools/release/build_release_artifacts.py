#!/usr/bin/env python3
"""Build deterministic release artifacts and generate SBOM + signatures."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def read_version() -> str:
    return Path("VERSION").read_text(encoding="utf-8").strip()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


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


def generate_spdx(artifacts: list[dict[str, str]], version: str, commit: str) -> dict:
    created = dt.datetime.now(tz=dt.timezone.utc).isoformat()
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


def build_release(args: argparse.Namespace) -> int:
    version = args.version or read_version()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    commit = git_commit()
    tag = args.tag or git_tag()

    if tag and tag != f"v{version}":
        raise RuntimeError(
            f"Git tag {tag} does not match VERSION v{version}. Update VERSION or use --tag."
        )

    source_archive = build_source_archive(output_dir, tag, version)

    artifacts = [
        {
            "name": source_archive.name,
            "path": str(source_archive),
            "sha256": sha256sum(source_archive),
            "size": str(source_archive.stat().st_size),
        }
    ]

    sbom_path = output_dir / f"TinyLanguage-v{version}-sbom.spdx.json"
    sbom_payload = generate_spdx(artifacts, version, commit)
    sbom_path.write_text(json.dumps(sbom_payload, indent=2) + "\n", encoding="utf-8")

    artifacts.append(
        {
            "name": sbom_path.name,
            "path": str(sbom_path),
            "sha256": sha256sum(sbom_path),
            "size": str(sbom_path.stat().st_size),
        }
    )

    checksums_path = output_dir / "SHA256SUMS"
    with checksums_path.open("w", encoding="utf-8") as handle:
        for artifact in artifacts:
            handle.write(f"{artifact['sha256']}  {artifact['name']}\n")

    build_info = {
        "version": version,
        "git": {
            "commit": commit,
            "tag": tag,
            "dirty": git_dirty(),
        },
        "build": {
            "timestamp_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": sys.version.replace("\n", " "),
        },
        "artifacts": artifacts,
    }

    signature_files: list[str] = []
    if args.sign:
        signature_files = sign_files(
            [Path(a["path"]) for a in artifacts] + [checksums_path],
            args.gpg_key_id,
        )
        build_info["signatures"] = signature_files
        build_info["signing"] = {
            "gpg_key_id": args.gpg_key_id,
        }

    build_info_path = output_dir / "build-info.json"
    build_info_path.write_text(
        json.dumps(build_info, indent=2) + "\n", encoding="utf-8"
    )

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
    parser.add_argument(
        "--gpg-key-id",
        default=os.environ.get("GPG_KEY_ID"),
        help="GPG key id/email for signing (or set GPG_KEY_ID).",
    )

    args = parser.parse_args()
    return build_release(args)


if __name__ == "__main__":
    raise SystemExit(main())
