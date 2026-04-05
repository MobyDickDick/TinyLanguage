"""Create TinyLanguage demo programs periodically.

This module is intentionally conservative: it uses a curated local template
catalog and does not execute downloaded code. It is a foundation for a
"program idea daemon" that can be extended with additional providers.
"""

from __future__ import annotations

import argparse
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tiny_program_repository_db_adapter import TinyProgramRepositoryDB


ASSIGNMENT_PATTERN = re.compile(r"^\s*(?:def\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
KEYWORDS = {"def", "fn", "if", "while", "return", "print", "true", "false", "null"}


@dataclass(frozen=True)
class ProgramIdea:
    """Represents one Tiny program template candidate."""

    slug: str
    title: str
    category: str
    description: str
    template: str


DEFAULT_IDEAS: tuple[ProgramIdea, ...] = (
    ProgramIdea(
        slug="nand-gate",
        title="Boolean NAND gate demo",
        category="logic",
        description="Computes NAND(a, b) with simple boolean arithmetic.",
        template="""// Auto-generated Tiny program: Boolean NAND gate demo
// Category: logic

fn nand(a, b) {
    // NAND is equivalent to NOT(a AND b)
    if (a == 1) {
        if (b == 1) {
            return 0;
        }
    }
    return 1;
}

def _unused1 = print(nand(0, 0));
def out1 = nand(0, 1);
def out2 = nand(1, 0);
def out3 = nand(1, 1);
def _unused2 = print(out1);
def _unused3 = print(out2);
def _unused4 = print(out3);
""",
    ),
    ProgramIdea(
        slug="linear-equation",
        title="Linear equation solver",
        category="math",
        description="Solves a*x + b = 0 and prints the solution.",
        template="""// Auto-generated Tiny program: Linear equation solver
// Category: math

fn solve_linear(a, b) {
    if (a == 0) {
        return "no unique solution";
    }
    return (0 - b) / a;
}

def solution = solve_linear(2, -10);
def _unused = print(solution);
""",
    ),
    ProgramIdea(
        slug="logistic-map",
        title="Logistic map simulation",
        category="physics-simulation",
        description="Runs a short chaotic-system simulation (logistic map).",
        template="""// Auto-generated Tiny program: Logistic map simulation
// Category: physics-simulation

fn iterate_logistic(seed, growth, steps) {
    def x = seed;
    def i = 0;
    while (i < steps) {
        x = growth * x * (1 - x);
        def _unused_print = print(x);
        i = i + 1;
    }
    return x;
}

def _unused = iterate_logistic(0.35, 3.7, 8);
""",
    ),
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


class TinyProgramGenerator:
    """Writes generated Tiny programs to an output directory."""

    def __init__(
        self,
        output_dir: Path,
        *,
        ideas: tuple[ProgramIdea, ...] = DEFAULT_IDEAS,
        seed: int | None = None,
        repository_db: TinyProgramRepositoryDB | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ideas = ideas
        self._rng = random.Random(seed)
        self._repository_db = repository_db

    @staticmethod
    def validate_program(source_text: str) -> ValidationReport:
        """Validate generated source against conservative quality gates."""
        issues: list[ValidationIssue] = []
        assigned_vars: set[str] = set()
        read_vars: set[str] = set()

        for raw_line in source_text.splitlines():
            line = raw_line.split("//", 1)[0].strip()
            if not line:
                continue
            match = ASSIGNMENT_PATTERN.match(line)
            assigned_var = match.group(1) if match else None
            if assigned_var is not None:
                assigned_vars.add(assigned_var)

            for name in IDENTIFIER_PATTERN.findall(line):
                if name in KEYWORDS:
                    continue
                if assigned_var is not None and name == assigned_var:
                    continue
                read_vars.add(name)

            if "while (true)" in line or "while (1)" in line:
                issues.append(
                    ValidationIssue(
                        "infinite_loop_literal",
                        "Programm enthält eine potenziell unendliche Schleife (while true/1).",
                    )
                )
            if line.startswith("goto "):
                target = line[len("goto ") :].strip().rstrip(";")
                if target and f"{target}:" in source_text:
                    issues.append(
                        ValidationIssue(
                            "possible_infinite_goto_cycle",
                            "Programm enthält ein direktes goto auf ein Label; Loop-Terminierung unklar.",
                        )
                    )
            if "throw " in line:
                issues.append(
                    ValidationIssue(
                        "uncaught_exception",
                        "Programm enthält 'throw' und kann unbehandelte Ausnahmen erzeugen.",
                    )
                )
            if re.search(r"/\s*0\b", line):
                issues.append(
                    ValidationIssue(
                        "division_by_zero_literal",
                        "Programm enthält eine mögliche Division durch 0.",
                    )
                )
            if "spawn " in line and "join(" not in source_text:
                issues.append(
                    ValidationIssue(
                        "possible_deadlock",
                        "Programm nutzt Nebenläufigkeit (spawn), aber kein join-Muster wurde erkannt.",
                    )
                )

        dead_stores = sorted(name for name in assigned_vars if name not in read_vars and not name.startswith("_unused"))
        if dead_stores:
            issues.append(
                ValidationIssue(
                    "dead_store",
                    f"Variablen beschrieben aber nicht gelesen: {', '.join(dead_stores)}",
                )
            )

        return ValidationReport(tuple(issues))

    def _select_idea(self, slug: str | None) -> ProgramIdea:
        if slug is None:
            return self._rng.choice(self._ideas)

        for idea in self._ideas:
            if idea.slug == slug:
                return idea
        available = ", ".join(sorted(idea.slug for idea in self._ideas))
        raise ValueError(f"Unknown idea slug '{slug}'. Available slugs: {available}")

    def create_program(self, *, slug: str | None = None) -> Path:
        """Generate one Tiny source file and return its path."""
        idea = self._select_idea(slug)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self.output_dir / f"{timestamp}_{idea.slug}.tiny"

        header = "\n".join(
            [
                f"// Generated at: {datetime.now(timezone.utc).isoformat()}",
                f"// Idea: {idea.title}",
                f"// Description: {idea.description}",
                "",
            ]
        )
        source_text = header + idea.template
        validation_report = self.validate_program(source_text)
        if not validation_report.is_valid:
            rendered = ", ".join(f"{issue.code}: {issue.message}" for issue in validation_report.issues)
            raise ValueError(f"Generated program failed validation: {rendered}")
        destination.write_text(source_text, encoding="utf-8")

        if self._repository_db is not None:
            existing_id = self._repository_db.find_equivalent_program_id(source_text)
            if existing_id is not None:
                raise ValueError(
                    f"Program already exists in DB as program_id={existing_id}; refusing duplicate insert."
                )
            self._repository_db.register_program(destination.stem, source_text)
        return destination


class TinyProgramDaemon:
    """Periodically invokes :class:`TinyProgramGenerator`."""

    def __init__(
        self,
        generator: TinyProgramGenerator,
        *,
        interval_seconds: int = 1800,
        slug: str | None = None,
    ) -> None:
        if interval_seconds < 0:
            raise ValueError("interval_seconds must be >= 0")
        self.generator = generator
        self.interval_seconds = interval_seconds
        self.slug = slug

    def run_once(self) -> Path:
        generated = self.generator.create_program(slug=self.slug)
        print(f"[tiny-program-daemon] Generated: {generated}")
        return generated

    def run_forever(self, *, max_runs: int | None = None) -> list[Path]:
        """Run periodically. ``max_runs`` allows finite runs for testing."""
        produced: list[Path] = []
        runs = 0
        while True:
            produced.append(self.run_once())
            runs += 1
            if max_runs is not None and runs >= max_runs:
                return produced
            time.sleep(self.interval_seconds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate TinyLanguage programs in fixed intervals. "
            "Default interval is 1800 seconds (30 minutes)."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="generated_tiny_programs",
        help="Directory for generated .tiny files (default: generated_tiny_programs)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=1800,
        help="Seconds between generations (default: 1800 = 30 minutes)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Generate only N programs and exit (useful for tests or cron jobs)",
    )
    parser.add_argument(
        "--idea",
        default=None,
        help="Optional idea slug (e.g. nand-gate, linear-equation, logistic-map)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible idea selection",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Optional SQLite DB path; when set, generated programs are persisted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repository_db: TinyProgramRepositoryDB | None = None
    if args.db_path:
        repository_db = TinyProgramRepositoryDB(Path(args.db_path))
        repository_db.initialize_schema()
    generator = TinyProgramGenerator(
        Path(args.output_dir),
        seed=args.seed,
        repository_db=repository_db,
    )
    daemon = TinyProgramDaemon(
        generator,
        interval_seconds=args.interval_seconds,
        slug=args.idea,
    )
    try:
        daemon.run_forever(max_runs=args.count)
    finally:
        if repository_db is not None:
            repository_db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
