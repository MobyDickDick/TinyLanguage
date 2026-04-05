"""Create TinyLanguage demo programs periodically.

This module is intentionally conservative: it uses a curated local template
catalog and does not execute downloaded code. It is a foundation for a
"program idea daemon" that can be extended with additional providers.
"""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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
def _unused2 = print(nand(0, 1));
def _unused3 = print(nand(1, 0));
def _unused4 = print(nand(1, 1));
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

def _unused = print(solve_linear(2, -10));
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


class TinyProgramGenerator:
    """Writes generated Tiny programs to an output directory."""

    def __init__(
        self,
        output_dir: Path,
        *,
        ideas: tuple[ProgramIdea, ...] = DEFAULT_IDEAS,
        seed: int | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ideas = ideas
        self._rng = random.Random(seed)

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
        destination.write_text(header + idea.template, encoding="utf-8")
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generator = TinyProgramGenerator(Path(args.output_dir), seed=args.seed)
    daemon = TinyProgramDaemon(
        generator,
        interval_seconds=args.interval_seconds,
        slug=args.idea,
    )
    daemon.run_forever(max_runs=args.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
