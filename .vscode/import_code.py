import argparse
import zipfile
from pathlib import Path

EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", "venv", "dist"}


def should_exclude(path: Path) -> bool:
    """Return True if any part of the path is in the excluded set."""
    return any(part in EXCLUDED_PARTS for part in path.parts)


def build_archive(output: Path) -> Path:
    project_root = Path(__file__).resolve().parent.parent
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in project_root.rglob("*"):
            if should_exclude(path.relative_to(project_root)):
                continue
            if path.is_file():
                zf.write(path, arcname=path.relative_to(project_root))
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a downloadable TinyLanguage archive.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/tinylanguage_bundle.zip"),
        help="Output zip path (default: dist/tinylanguage_bundle.zip)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_path = build_archive(args.output)
    print(f"Created archive at {archive_path}")


if __name__ == "__main__":
    main()
