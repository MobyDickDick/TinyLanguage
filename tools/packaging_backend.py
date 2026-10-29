"""Setuptools PEP 517 hooks with reproducible source-archive metadata.

Wheels already honor SOURCE_DATE_EPOCH. Normalize sdist ordering, ownership,
permissions and the gzip header too, without putting generated runtime files
in either distribution. Release builds supply the tagged commit's epoch.
"""

import gzip
import io
import os
from pathlib import Path
import tarfile

from setuptools import build_meta as _backend
from setuptools.build_meta import (  # noqa: F401 - PEP 517 hooks
    build_wheel,
    get_requires_for_build_sdist,
    get_requires_for_build_wheel,
    prepare_metadata_for_build_wheel,
)


def build_sdist(sdist_directory, config_settings=None):
    name = _backend.build_sdist(sdist_directory, config_settings)
    path = Path(sdist_directory) / name
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "315532800"))
    buffer = io.BytesIO()
    with tarfile.open(path, "r:gz") as source:
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as target:
            for member in sorted(source.getmembers(), key=lambda entry: entry.name):
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.mtime = epoch
                member.mode = 0o755 if member.isdir() else 0o644
                member.pax_headers = {}
                target.addfile(member, source.extractfile(member) if member.isfile() else None)
    with path.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=epoch) as archive:
            archive.write(buffer.getvalue())
    return name
