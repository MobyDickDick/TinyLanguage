#!/usr/bin/env python3
"""Summarize converter strategy outcomes from element validation/optimization logs."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

SUCCESS_PATTERNS = (
    "Geometrie nach Elementabgleich aktualisiert",
    "Parameter nach Mittelpunkt/Diagonale angepasst",
    "Bracketing ",
    "Joint-Multistart ",
)
FAIL_PATTERNS = (
    "keine relevante Änderung",
    "verworfen",
    "abgebrochen",
)
FIXED_PATTERNS = (
    "übersprungen",
    "Farben gesperrt",
    "Range=",
)


def classify_outcome(line: str) -> str | None:
    if any(k in line for k in FIXED_PATTERNS):
        return "fixed_rule"
    if any(k in line for k in FAIL_PATTERNS):
        return "failed"
    if "->" in line and any(k in line for k in SUCCESS_PATTERNS):
        return "success"
    if any(k in line for k in SUCCESS_PATTERNS):
        return "adjustable_step"
    return None


def detect_strategy(line: str) -> str | None:
    text = line.lower()
    if "mittelpunkt/diagonale" in text:
        return "center_diagonal_update"
    if "joint-multistart" in text:
        return "joint_multistart"
    if "radius-bracketing" in text:
        return "radius_bracketing"
    if "mittelpunkt-bracketing" in text:
        return "center_bracketing"
    if "breiten-bracketing" in text:
        return "width_bracketing"
    if "längen-bracketing" in text:
        return "length_bracketing"
    if "farb-bracketing" in text:
        return "color_bracketing"
    if "breitenkorrektur" in text:
        return "iterative_width_correction"
    if "geometrie nach elementabgleich aktualisiert" in text:
        return "geometry_sync"
    if "nachkorrektur fokussiert" in text:
        return "focused_post_correction"
    return None


def parse_file(path: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("Runde "):
            continue
        strategy = detect_strategy(line)
        outcome = classify_outcome(line)
        if strategy is None or outcome is None:
            continue
        element = line.split(":", 1)[0] if ":" in line else "global"
        records.append(
            {
                "file": path.name,
                "mode": "validation" if "validation" in path.name else "optimization",
                "element": element,
                "strategy": strategy,
                "outcome": outcome,
                "line": line,
            }
        )
    return records


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "mode", "element", "strategy", "outcome", "line"], delimiter=";")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[tuple[str, str], str] = {}
    for row in rows:
        by_strategy[row["strategy"]][row["outcome"]] += 1
        key = (row["strategy"], row["outcome"])
        examples.setdefault(key, row["line"])

    lines = [
        "# Strategien-Auswertung (AC0800..AC0884)",
        "",
        "Diese Übersicht kategorisiert Logzeilen in erfolgreiche/erfolglose/fixierte bzw. anpassbare Schritte.",
        "",
        "## Strategiematrix",
        "",
        "| Strategie | Erfolgreich | Erfolglos | Fix geregelt | Anpassbar (neutral) |",
        "|---|---:|---:|---:|---:|",
    ]

    for strategy in sorted(by_strategy):
        c = by_strategy[strategy]
        lines.append(
            f"| {strategy} | {c['success']} | {c['failed']} | {c['fixed_rule']} | {c['adjustable_step']} |"
        )

    lines.extend(["", "## Interpretation für Skript-Verbesserungen", ""])
    for strategy in sorted(by_strategy):
        c = by_strategy[strategy]
        verdict = "erfolgreich" if c["success"] > c["failed"] else "kritisch"
        lines.append(f"- **{strategy}**: Status **{verdict}** (success={c['success']}, failed={c['failed']}, fixed={c['fixed_rule']}).")
        if (strategy, "failed") in examples:
            lines.append(f"  - Negativbeispiel: `{examples[(strategy, 'failed')]}`")
        if (strategy, "success") in examples:
            lines.append(f"  - Positivbeispiel: `{examples[(strategy, 'success')]}`")
        if c["fixed_rule"]:
            lines.append("  - Hinweis: enthält fixierte Randbedingungen (aktuell nicht dynamisch).")

    lines.extend(
        [
            "",
            "## Was ist fix geregelt vs. anpassbar?",
            "",
            "- **Fix geregelt**: Zeilen mit `übersprungen`, `Farben gesperrt` oder `Range=min..max` mit identischen Grenzen.",
            "- **Anpassbar**: Bracketing-/Korrektur-/Update-Schritte ohne Sperre.",
            "",
            "## Verbesserungsansätze",
            "",
            "1. Bei Strategien mit vielen `keine relevante Änderung` Suchraum/Startwerte adaptiv erweitern.",
            "2. Für `verworfen`-Meldungen Box-Check-Schwellen dynamisch an Symbolgröße koppeln.",
            "3. Für häufig fixierte Strategien (v. a. Farbe/Breite) optionalen `unlock`-Modus pro Referenz erlauben.",
            "4. Strategien mit häufigem Erfolg als erste Stufe priorisieren, um Iterationen zu sparen.",
            "",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", default="artifacts/converted_symbols/reports")
    parser.add_argument(
        "--out-csv",
        default="artifacts/converted_symbols/reports/AC0800_AC0884_strategy_events.csv",
    )
    parser.add_argument(
        "--out-md",
        default="artifacts/converted_symbols/reports/AC0800_AC0884_strategy_summary.md",
    )
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    log_files = sorted(reports_dir.glob("*_element_validation.log")) + sorted(reports_dir.glob("*_element_optimization.log"))

    rows: list[dict[str, str]] = []
    for path in log_files:
        rows.extend(parse_file(path))

    write_csv(Path(args.out_csv), rows)
    write_markdown(Path(args.out_md), rows)
    print(f"processed_logs={len(log_files)}")
    print(f"strategy_events={len(rows)}")
    print(f"wrote_csv={args.out_csv}")
    print(f"wrote_md={args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
