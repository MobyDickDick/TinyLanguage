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
WHILE_PATTERN = re.compile(r"\bwhile\s*\((.*?)\)\s*\{")
COMPARISON_PATTERN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:<|<=|>|>=|!=)\s*.+$"
)
DIVISOR_PATTERN = re.compile(
    r"/\s*\(?\s*(?P<divisor>[A-Za-z_][A-Za-z0-9_]*|[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
)
HEAP_ALLOCATION_PATTERN = re.compile(r"\bnew\s*(?:\(\s*([^)]*)\s*\)|\[([^]]*)\])")
LOOP_BOUND_PATTERN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(<|<=|>|>=)\s*"
    r"([A-Za-z_][A-Za-z0-9_]*|[+-]?\d+)\s*$"
)
MAX_GENERATED_HEAP_SLOTS = 4096
MAX_GENERATED_LOOP_ITERATIONS = 10_000
NONDETERMINISTIC_RANDOM_CALL_PATTERN = re.compile(
    r"\b(?:Random|random)\s*\.\s*(?:random|randint|choice|shuffle|uniform|seed)\s*\("
)
NONDETERMINISTIC_TIME_CALL_PATTERN = re.compile(
    r"\b(?:Time|time)\s*\.\s*(?:now_ms|now_iso|monotonic_ms|time|time_ns|monotonic)\s*\("
)
DECLARED_NAME_PATTERN = re.compile(
    r"^\s*(?:def|fn)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE
)
SNAKE_CASE_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")
PROGRAM_LINE_LIMITS = {
    "logic": 80,
    "math": 80,
    "physics-simulation": 100,
}
DEFAULT_PROGRAM_LINE_LIMIT = 100
GENERATED_COMMENT_PREFIXES = (
    "auto-generated tiny program:",
    "category:",
    "description:",
    "generated at:",
    "idea:",
)


def _code_without_comments_or_strings(source_text: str) -> str:
    """Remove text that cannot contain executable nondeterministic calls."""
    without_comments = re.sub(r"//[^\n]*", "", source_text)
    return re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', without_comments)


def _loop_regions(source_text: str) -> tuple[tuple[str, str], ...]:
    """Return ``(condition, body)`` pairs for balanced, structured loops.

    A loop body is the cyclic region (SCC) of Tiny's structured control-flow
    graph.  Extracting complete regions instead of inspecting individual lines
    lets the quality gate reason about progress across nested blocks.
    """
    code = re.sub(r"//[^\n]*", "", source_text)
    regions: list[tuple[str, str]] = []
    for match in WHILE_PATTERN.finditer(code):
        opening_brace = match.end() - 1
        depth = 1
        cursor = opening_brace + 1
        while cursor < len(code) and depth:
            if code[cursor] == "{":
                depth += 1
            elif code[cursor] == "}":
                depth -= 1
            cursor += 1
        if depth == 0:
            regions.append((match.group(1).strip(), code[opening_brace + 1 : cursor - 1]))
    return tuple(regions)


def _loop_has_progress(condition: str, body: str) -> bool:
    """Prove a basic induction-variable update in a loop's cyclic region."""
    match = COMPARISON_PATTERN.match(condition)
    if match is None:
        return False
    variable = re.escape(match.group(1))
    return bool(
        re.search(rf"\b{variable}\s*=\s*{variable}\s*[+-]\s*[^;]+", body)
        or re.search(rf"\b{variable}\s*[+-]=\s*[^;]+", body)
    )


def _latest_integer_assignment(source_prefix: str, variable: str) -> int | None:
    """Return the latest literal integer assigned to ``variable``."""
    assignments = list(
        re.finditer(
            rf"\b(?:def\s+)?{re.escape(variable)}\s*=\s*([+-]?\d+)\s*;",
            source_prefix,
        )
    )
    return int(assignments[-1].group(1)) if assignments else None


def _loop_iteration_bound(source_prefix: str, condition: str, body: str) -> int | None:
    """Conservatively derive an upper iteration count for a simple loop."""
    match = LOOP_BOUND_PATTERN.match(condition)
    if match is None:
        return None
    variable, operator, bound_expression = match.groups()
    start = _latest_integer_assignment(source_prefix, variable)
    try:
        bound = int(bound_expression)
    except ValueError:
        bound = _latest_integer_assignment(source_prefix, bound_expression)
    if start is None or bound is None:
        return None

    updates = list(
        re.finditer(
            rf"\b{re.escape(variable)}\s*=\s*{re.escape(variable)}\s*([+-])\s*(\d+)\s*;",
            body,
        )
    )
    if len(updates) != 1:
        return None
    sign, magnitude = updates[0].groups()
    step = int(magnitude) * (1 if sign == "+" else -1)
    distance = bound - start
    if operator in {"<", "<="} and step > 0:
        distance += 1 if operator == "<=" else 0
    elif operator in {">", ">="} and step < 0:
        distance = -distance + (1 if operator == ">=" else 0)
        step = -step
    else:
        return None
    return max(0, (distance + step - 1) // step)


def _divisor_is_proven_nonzero(source_prefix: str, divisor: str) -> bool:
    """Return whether simple local evidence proves ``divisor`` is non-zero.

    The generator deliberately does not pretend to be a full type checker.  It
    accepts numeric constants, a latest literal assignment, or an earlier
    zero-check whose branch necessarily returns.  Restricting the search to the
    current function prevents a guard in a sibling function from being reused.
    """
    try:
        return float(divisor) != 0
    except ValueError:
        pass

    function_start = source_prefix.rfind("fn ")
    local_prefix = source_prefix[function_start:] if function_start >= 0 else source_prefix
    escaped = re.escape(divisor)
    assignments = list(
        re.finditer(
            rf"\b(?:def\s+)?{escaped}\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*;",
            local_prefix,
        )
    )
    last_assignment = assignments[-1] if assignments else None
    guard_pattern = re.compile(
        rf"\bif\s*\(\s*{escaped}\s*==\s*0(?:\.0*)?\s*\)\s*\{{[^{{}}]*\breturn\b[^{{}}]*\}}",
        re.DOTALL,
    )
    guards = list(guard_pattern.finditer(local_prefix))
    last_guard = guards[-1] if guards else None
    if last_guard is not None and (
        last_assignment is None or last_guard.end() > last_assignment.end()
    ):
        return True
    return last_assignment is not None and float(last_assignment.group(1)) != 0


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

// A zero coefficient has no unique solution, so handle it before division.
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

// Print each state of a bounded logistic-map simulation.
fn iterate_logistic(seed, growth, steps) {
    def x = seed;
    def i = 0;
    while (i < 8) {
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
        deterministic_profile: bool = False,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ideas = ideas
        self._rng = random.Random(seed)
        self._repository_db = repository_db
        self._deterministic_profile = deterministic_profile

    @staticmethod
    def validate_program(
        source_text: str,
        *,
        deterministic_profile: bool = False,
        category: str | None = None,
    ) -> ValidationReport:
        """Validate generated source against conservative quality gates."""
        issues: list[ValidationIssue] = []
        assigned_vars: set[str] = set()
        read_vars: set[str] = set()
        code = re.sub(r"//[^\n]*", "", source_text)

        comments = re.findall(r"^\s*//\s*(\S.*)$", source_text, re.MULTILINE)
        explanatory_comments = [
            comment
            for comment in comments
            if not comment.casefold().startswith(GENERATED_COMMENT_PREFIXES)
        ]
        if not explanatory_comments:
            issues.append(
                ValidationIssue(
                    "missing_explanatory_comment",
                    "Das Programm benötigt mindestens einen erklärenden Kommentar.",
                )
            )

        invalid_names = sorted(
            {
                match.group(1)
                for match in DECLARED_NAME_PATTERN.finditer(code)
                if not SNAKE_CASE_NAME_PATTERN.fullmatch(match.group(1))
            }
        )
        if invalid_names:
            issues.append(
                ValidationIssue(
                    "non_snake_case_name",
                    "Deklarierte Namen müssen snake_case verwenden: "
                    + ", ".join(invalid_names),
                )
            )

        line_limit = PROGRAM_LINE_LIMITS.get(category, DEFAULT_PROGRAM_LINE_LIMIT)
        line_count = len(source_text.splitlines())
        if line_count > line_limit:
            category_label = category or "default"
            issues.append(
                ValidationIssue(
                    "program_too_long",
                    f"Programm der Kategorie '{category_label}' überschreitet "
                    f"{line_limit} Zeilen ({line_count}).",
                )
            )

        if deterministic_profile:
            executable_code = _code_without_comments_or_strings(source_text)
            if NONDETERMINISTIC_RANDOM_CALL_PATTERN.search(executable_code):
                issues.append(
                    ValidationIssue(
                        "nondeterministic_random_source",
                        "Das Determinismus-Profil verbietet Zufallsquellen.",
                    )
                )
            if NONDETERMINISTIC_TIME_CALL_PATTERN.search(executable_code):
                issues.append(
                    ValidationIssue(
                        "nondeterministic_time_source",
                        "Das Determinismus-Profil verbietet Zeitquellen.",
                    )
                )

        for allocation in HEAP_ALLOCATION_PATTERN.finditer(code):
            size_expression, literal_items = allocation.groups()
            if literal_items is not None:
                size = 0 if not literal_items.strip() else len(literal_items.split(","))
            else:
                try:
                    size = int(size_expression.strip())
                except (AttributeError, ValueError):
                    size = None
            if size is None or size < 0:
                issues.append(
                    ValidationIssue(
                        "heap_bound_unproven",
                        "Für eine Heap-Allokation ist keine nichtnegative feste Obergrenze nachweisbar.",
                    )
                )
            elif size > MAX_GENERATED_HEAP_SLOTS:
                issues.append(
                    ValidationIssue(
                        "heap_bound_exceeded",
                        f"Heap-Allokation überschreitet {MAX_GENERATED_HEAP_SLOTS} Elemente.",
                    )
                )

        for division in DIVISOR_PATTERN.finditer(code):
            divisor = division.group("divisor")
            if re.fullmatch(r"[+-]?(?:0+(?:\.0*)?|\.0+)", divisor):
                issues.append(
                    ValidationIssue(
                        "division_by_zero_literal",
                        "Programm enthält eine mögliche Division durch 0.",
                    )
                )
            elif not _divisor_is_proven_nonzero(code[: division.start()], divisor):
                issues.append(
                    ValidationIssue(
                        "division_nonzero_unproven",
                        f"Für den Divisor '{divisor}' ist kein von Null verschiedener Wert nachweisbar.",
                    )
                )

        for condition, body in _loop_regions(source_text):
            normalized_condition = re.sub(r"\s+", "", condition).lower()
            if normalized_condition in {"true", "1"}:
                issues.append(
                    ValidationIssue(
                        "infinite_loop_literal",
                        "Programm enthält eine potenziell unendliche Schleife (while true/1).",
                    )
                )
            elif not _loop_has_progress(condition, body):
                issues.append(
                    ValidationIssue(
                        "loop_termination_unproven",
                        "Für eine Schleife ist keine fortschreitende Induktionsvariable nachweisbar.",
                    )
                )
            else:
                loop_start = code.find(f"while ({condition})")
                source_prefix = code[:loop_start] if loop_start >= 0 else code
                iteration_bound = _loop_iteration_bound(source_prefix, condition, body)
                if iteration_bound is None:
                    issues.append(
                        ValidationIssue(
                            "loop_resource_bound_unproven",
                            "Für eine Schleife ist keine feste Iterationsobergrenze nachweisbar.",
                        )
                    )
                elif iteration_bound > MAX_GENERATED_LOOP_ITERATIONS:
                    issues.append(
                        ValidationIssue(
                            "loop_resource_bound_exceeded",
                            f"Schleife überschreitet {MAX_GENERATED_LOOP_ITERATIONS} Iterationen.",
                        )
                    )

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
        validation_report = self.validate_program(
            source_text,
            deterministic_profile=self._deterministic_profile,
            category=idea.category,
        )
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
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Reject generated programs that use time or random sources.",
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
        deterministic_profile=args.deterministic,
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
