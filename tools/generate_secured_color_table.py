#!/usr/bin/env python3
"""Generate a table of stable flat colors from converted SVG symbols."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

SVG_DIR = Path("artifacts/converted_symbols/svg")
OUT_MD = Path("docs/secured_colors_table.md")

HEX_RE = re.compile(r'(fill|stroke)="(#[0-9a-fA-F]{6})"')
TAG_RE = re.compile(r'<(circle|line|rect|path)\b[^>]*>')


def rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))


def main() -> int:
    color_files: dict[str, set[str]] = defaultdict(set)
    color_roles: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for svg_path in sorted(SVG_DIR.glob("*.svg")):
        text = svg_path.read_text(encoding="utf-8")
        for tag_match in TAG_RE.finditer(text):
            tag = tag_match.group(0)
            shape = tag_match.group(1)
            for role, color in HEX_RE.findall(tag):
                color = color.lower()
                color_files[color].add(svg_path.name)
                color_roles[color][f"{shape}.{role}"] += 1

    rows = []
    for color, files in color_files.items():
        r, g, b = rgb(color)
        rows.append(
            {
                "color": color,
                "files": len(files),
                "gray": r == g == b,
                "roles": dict(sorted(color_roles[color].items())),
            }
        )

    rows.sort(key=lambda x: (-x["files"], x["color"]))
    secured = [r for r in rows if r["files"] >= 10]

    lines: list[str] = []
    lines.append("# Gesicherte Farbtabelle (flächige Farben ohne Verläufe)")
    lines.append("")
    lines.append("Quelle: Analyse der konvertierten SVG-Symbole in `artifacts/converted_symbols/svg`. ")
    lines.append("Als *gesichert* gelten hier Farben, die in vielen Symbolen wiederkehren (>=10 Dateien) und als flache `fill`/`stroke`-Farben auftreten.")
    lines.append("")
    lines.append("| Farbe | RGB | Dateien | Häufige Rollen |")
    lines.append("|---|---:|---:|---|")
    for row in secured:
        role_text = ", ".join(f"`{k}`×{v}" for k, v in row["roles"].items())
        r, g, b = rgb(row["color"])
        lines.append(f"| `{row['color']}` | ({r},{g},{b}) | {row['files']} | {role_text} |")

    lines.append("")
    lines.append("## Vollständige Rangliste (Top 20)")
    lines.append("")
    lines.append("| Farbe | Dateien |")
    lines.append("|---|---:|")
    for row in rows[:20]:
        lines.append(f"| `{row['color']}` | {row['files']} |")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
