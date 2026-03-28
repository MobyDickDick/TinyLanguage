from __future__ import annotations

import argparse
import base64
import csv
import struct
from dataclasses import dataclass
from pathlib import Path

FAILED_SUFFIX = "_failed.png"
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff")
MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


@dataclass
class RetryResult:
    failed_diff: str
    source_image: str
    output_svg: str
    status: str
    detail: str


def _stem_from_failed_diff_name(name: str) -> str | None:
    if not name.endswith(FAILED_SUFFIX):
        return None
    stem = name[: -len(FAILED_SUFFIX)]
    if stem.endswith("_diff"):
        stem = stem[: -len("_diff")]
    return stem or None


def _find_source_image(stem: str, source_dir: Path) -> Path | None:
    exact: list[Path] = []
    prefix: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        exact.extend(sorted(source_dir.glob(f"{stem}{ext}")))
        exact.extend(sorted(source_dir.glob(f"{stem}{ext.upper()}")))
        prefix.extend(sorted(source_dir.glob(f"{stem}_*{ext}")))
        prefix.extend(sorted(source_dir.glob(f"{stem}_*{ext.upper()}")))

    if exact:
        return exact[0]
    if prefix:
        return prefix[0]
    return None


def _read_jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"{path} is not a JPEG file")

    i = 2
    while i < len(data):
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1

        if marker in (0xD8, 0xD9):
            continue
        if i + 2 > len(data):
            break
        seg_len = struct.unpack(">H", data[i : i + 2])[0]
        if seg_len < 2 or i + seg_len > len(data):
            break

        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 7 > len(data):
                break
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            return width, height

        i += seg_len

    raise ValueError(f"Could not read JPEG dimensions from {path}")


def _read_png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG file")
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def _read_gif_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError(f"{path} is not a GIF file")
    width, height = struct.unpack("<HH", data[6:10])
    return int(width), int(height)


def _read_bmp_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"{path} is not a BMP file")
    width, height = struct.unpack("<ii", data[18:26])
    return abs(int(width)), abs(int(height))


def _read_size(path: Path) -> tuple[int, int]:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return _read_jpeg_size(path)
    if ext == ".png":
        return _read_png_size(path)
    if ext == ".gif":
        return _read_gif_size(path)
    if ext == ".bmp":
        return _read_bmp_size(path)

    try:
        from PIL import Image

        with Image.open(path) as img:
            return int(img.width), int(img.height)
    except ModuleNotFoundError:
        pass

    raise ValueError(
        f"No built-in dimension reader for {path.suffix} and Pillow is not available."
    )


def _embedded_raster_svg(image_path: Path) -> str:
    width, height = _read_size(image_path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = MIME_BY_EXT.get(image_path.suffix.lower(), "application/octet-stream")
    href = f"data:{mime};base64,{encoded}"
    return (
        "<svg xmlns=\"http://www.w3.org/2000/svg\" "
        f"width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">\n"
        f"  <image href=\"{href}\" x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" />\n"
        "</svg>\n"
    )


def retry_failed_conversions(diff_dir: Path, source_dir: Path, output_dir: Path, overwrite: bool) -> list[RetryResult]:
    results: list[RetryResult] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for failed_diff in sorted(diff_dir.glob(f"*{FAILED_SUFFIX}")):
        stem = _stem_from_failed_diff_name(failed_diff.name)
        if not stem:
            continue

        source_image = _find_source_image(stem, source_dir)
        output_svg = output_dir / f"{stem}.svg"

        if source_image is None:
            results.append(
                RetryResult(
                    failed_diff=failed_diff.name,
                    source_image="",
                    output_svg=output_svg.name,
                    status="missing_source",
                    detail=f"No source image found for '{stem}'.",
                )
            )
            continue

        if output_svg.exists() and not overwrite:
            results.append(
                RetryResult(
                    failed_diff=failed_diff.name,
                    source_image=source_image.name,
                    output_svg=output_svg.name,
                    status="skipped_existing",
                    detail="Output SVG already exists. Use --overwrite to replace it.",
                )
            )
            continue

        try:
            output_svg.write_text(_embedded_raster_svg(source_image), encoding="utf-8")
            results.append(
                RetryResult(
                    failed_diff=failed_diff.name,
                    source_image=source_image.name,
                    output_svg=output_svg.name,
                    status="recovered",
                    detail="Created embedded-raster SVG fallback.",
                )
            )
        except Exception as exc:  # pragma: no cover - protective path
            results.append(
                RetryResult(
                    failed_diff=failed_diff.name,
                    source_image=source_image.name,
                    output_svg=output_svg.name,
                    status="error",
                    detail=str(exc),
                )
            )

    return results


def _write_report(report_path: Path, results: list[RetryResult]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["failed_diff", "source_image", "output_svg", "status", "detail"])
        for row in results:
            writer.writerow([row.failed_diff, row.source_image, row.output_svg, row.status, row.detail])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Retry failed image conversions for diff images ending with '_failed.png' by creating "
            "embedded-raster SVG fallbacks."
        )
    )
    parser.add_argument("--diff-dir", type=Path, default=Path("artifacts/converted_images_diff"))
    parser.add_argument("--source-dir", type=Path, default=Path("artifacts/images_to_convert"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/converted_images_svg"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/converted_images_svg/retry_report.csv"))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    results = retry_failed_conversions(
        diff_dir=args.diff_dir,
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
    )
    _write_report(args.report, results)

    recovered = sum(1 for row in results if row.status == "recovered")
    total = len(results)
    print(f"processed={total} recovered={recovered} report={args.report}")


if __name__ == "__main__":
    main()
