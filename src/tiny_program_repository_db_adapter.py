"""SQLite adapter for an atomic Tiny-language program repository.

The schema stores one row per statement in `statements`, while instruction-specific
attributes are normalized into dedicated tables (print/set/goto/if_goto/label).
"""

from __future__ import annotations

import sqlite3
import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class ParsedStatement:
    """Normalized Tiny statement used for source/database conversions."""

    statement_kind: str
    raw_text: str
    payload: dict[str, Any]

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS programs (
    program_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    source_signature TEXT NOT NULL UNIQUE,
    source_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS statements (
    statement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    pc INTEGER NOT NULL,
    statement_kind TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    FOREIGN KEY (program_id) REFERENCES programs(program_id) ON DELETE CASCADE,
    UNIQUE (program_id, pc)
);

CREATE TABLE IF NOT EXISTS labels (
    statement_id INTEGER PRIMARY KEY,
    label_name TEXT NOT NULL,
    FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS print_statements (
    statement_id INTEGER PRIMARY KEY,
    value_expr TEXT NOT NULL,
    FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS set_statements (
    statement_id INTEGER PRIMARY KEY,
    var_name TEXT NOT NULL,
    value_expr TEXT NOT NULL,
    FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS goto_statements (
    statement_id INTEGER PRIMARY KEY,
    target_label TEXT NOT NULL,
    FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS if_goto_statements (
    statement_id INTEGER PRIMARY KEY,
    condition_expr TEXT NOT NULL,
    target_label TEXT NOT NULL,
    FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_statements_program_pc ON statements(program_id, pc);
CREATE INDEX IF NOT EXISTS idx_labels_program_name ON labels(label_name);
""".strip()


@dataclass(slots=True)
class StepResult:
    """Single execution step emitted by the repository workbench."""

    pc: int
    statement_kind: str
    statement_text: str
    output: str | None
    next_pc: int | None


class TinyProgramRepositoryDB:
    """Small SQLite adapter that stores and executes normalized Tiny-like programs."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the active SQLite connection."""
        self.connection.close()

    def initialize_schema(self) -> None:
        """Create all repository tables."""
        self.connection.executescript(SCHEMA_SQL)
        self.connection.commit()

    @staticmethod
    def parse_source_to_statements(source_text: str) -> list[ParsedStatement]:
        """Parse a small Tiny subset into normalized statements.

        Supported syntax per non-empty line:
        - `<label>:`
        - `print <expr>`
        - `set <var> = <expr>`
        - `goto <label>`
        - `if <expr> goto <label>`
        """

        statements: list[ParsedStatement] = []
        for line_no, raw_line in enumerate(source_text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.endswith(":"):
                label_name = line[:-1].strip()
                if not label_name:
                    raise ValueError(f"Line {line_no}: empty label is not allowed")
                statements.append(
                    ParsedStatement("label", f"{label_name}:", {"label_name": label_name})
                )
                continue

            if line.startswith("print "):
                value_expr = line[len("print ") :].strip()
                if not value_expr:
                    raise ValueError(f"Line {line_no}: print requires an expression")
                statements.append(
                    ParsedStatement("print", f"print {value_expr}", {"value_expr": value_expr})
                )
                continue

            if line.startswith("set "):
                assignment = line[len("set ") :]
                if "=" not in assignment:
                    raise ValueError(f"Line {line_no}: set requires '='")
                var_name, value_expr = assignment.split("=", 1)
                var_name = var_name.strip()
                value_expr = value_expr.strip()
                if not var_name or not value_expr:
                    raise ValueError(f"Line {line_no}: set requires variable and expression")
                statements.append(
                    ParsedStatement(
                        "set",
                        f"set {var_name} = {value_expr}",
                        {"var_name": var_name, "value_expr": value_expr},
                    )
                )
                continue

            if line.startswith("goto "):
                target_label = line[len("goto ") :].strip()
                if not target_label:
                    raise ValueError(f"Line {line_no}: goto requires a target label")
                statements.append(
                    ParsedStatement("goto", f"goto {target_label}", {"target_label": target_label})
                )
                continue

            if line.startswith("if ") and " goto " in line:
                condition_part, target_part = line[3:].split(" goto ", 1)
                condition_expr = condition_part.strip()
                target_label = target_part.strip()
                if not condition_expr or not target_label:
                    raise ValueError(f"Line {line_no}: if-goto requires condition and target")
                statements.append(
                    ParsedStatement(
                        "if_goto",
                        f"if {condition_expr} goto {target_label}",
                        {"condition_expr": condition_expr, "target_label": target_label},
                    )
                )
                continue

            raise ValueError(f"Line {line_no}: unsupported Tiny statement: {line}")

        return statements

    def source_to_db(self, program_name: str, source_text: str) -> int:
        """Convert Tiny source code into normalized DB rows and return program_id."""

        statements = self.parse_source_to_statements(source_text)
        program_id = self.register_program(program_name, source_text)
        for pc, statement in enumerate(statements):
            self.add_statement(
                program_id,
                pc,
                statement.statement_kind,
                statement.raw_text,
                statement.payload,
            )
        return program_id

    def db_to_source(self, program_id: int) -> str:
        """Reconstruct Tiny source from normalized DB rows."""

        rows = self.connection.execute(
            (
                "SELECT statement_id, statement_kind, raw_text "
                "FROM statements WHERE program_id = ? ORDER BY pc"
            ),
            (program_id,),
        ).fetchall()
        if not rows:
            raise ValueError(f"Program {program_id} has no statements")
        return "\n".join(str(row["raw_text"]) for row in rows)

    @classmethod
    def are_sources_equivalent(cls, source_a: str, source_b: str) -> bool:
        """Return True when both sources normalize to the same Tiny program."""

        parsed_a = cls.parse_source_to_statements(source_a)
        parsed_b = cls.parse_source_to_statements(source_b)
        if len(parsed_a) != len(parsed_b):
            return False
        for stmt_a, stmt_b in zip(parsed_a, parsed_b):
            if stmt_a.statement_kind != stmt_b.statement_kind:
                return False
            if stmt_a.payload != stmt_b.payload:
                return False
        return True

    def register_program(self, name: str, source_text: str) -> int:
        """Insert a program shell and return its id."""
        signature = self.normalized_source_signature(source_text)
        cur = self.connection.execute(
            "INSERT INTO programs(name, source_signature, source_text) VALUES (?, ?, ?)",
            (name, signature, source_text),
        )
        self.connection.commit()
        return int(cur.lastrowid)

    @classmethod
    def normalized_source_signature(cls, source_text: str) -> str:
        """Compute a stable signature for semantic duplicate detection."""
        try:
            normalized = [
                {
                    "kind": stmt.statement_kind,
                    "payload": stmt.payload,
                }
                for stmt in cls.parse_source_to_statements(source_text)
            ]
            canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        except ValueError:
            fallback_lines: list[str] = []
            for raw_line in source_text.splitlines():
                line = raw_line.split("//", 1)[0].split("#", 1)[0].strip()
                if line:
                    fallback_lines.append(line)
            canonical = "\n".join(fallback_lines)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def find_equivalent_program_id(self, source_text: str) -> int | None:
        """Return a stored program id with equivalent semantics, if any."""
        signature = self.normalized_source_signature(source_text)
        row = self.connection.execute(
            "SELECT program_id FROM programs WHERE source_signature = ?",
            (signature,),
        ).fetchone()
        if row is None:
            return None
        return int(row["program_id"])

    def add_statement(
        self,
        program_id: int,
        pc: int,
        statement_kind: str,
        raw_text: str,
        payload: dict[str, Any],
    ) -> int:
        """Insert one statement and its kind-specific payload."""
        cur = self.connection.execute(
            (
                "INSERT INTO statements(program_id, pc, statement_kind, raw_text) "
                "VALUES (?, ?, ?, ?)"
            ),
            (program_id, pc, statement_kind, raw_text),
        )
        statement_id = int(cur.lastrowid)

        if statement_kind == "label":
            self.connection.execute(
                "INSERT INTO labels(statement_id, label_name) VALUES (?, ?)",
                (statement_id, payload["label_name"]),
            )
        elif statement_kind == "print":
            self.connection.execute(
                "INSERT INTO print_statements(statement_id, value_expr) VALUES (?, ?)",
                (statement_id, payload["value_expr"]),
            )
        elif statement_kind == "set":
            self.connection.execute(
                (
                    "INSERT INTO set_statements(statement_id, var_name, value_expr) "
                    "VALUES (?, ?, ?)"
                ),
                (statement_id, payload["var_name"], payload["value_expr"]),
            )
        elif statement_kind == "goto":
            self.connection.execute(
                "INSERT INTO goto_statements(statement_id, target_label) VALUES (?, ?)",
                (statement_id, payload["target_label"]),
            )
        elif statement_kind == "if_goto":
            self.connection.execute(
                (
                    "INSERT INTO if_goto_statements(statement_id, condition_expr, target_label) "
                    "VALUES (?, ?, ?)"
                ),
                (statement_id, payload["condition_expr"], payload["target_label"]),
            )
        else:
            raise ValueError(f"Unsupported statement_kind: {statement_kind}")

        self.connection.commit()
        return statement_id

    def load_statement(self, program_id: int, pc: int) -> sqlite3.Row | None:
        """Load a statement by program and program counter."""
        cur = self.connection.execute(
            (
                "SELECT statement_id, statement_kind, raw_text, pc "
                "FROM statements WHERE program_id = ? AND pc = ?"
            ),
            (program_id, pc),
        )
        return cur.fetchone()

    def _label_to_pc(self, program_id: int, label_name: str) -> int:
        cur = self.connection.execute(
            (
                "SELECT s.pc FROM statements s "
                "JOIN labels l ON l.statement_id = s.statement_id "
                "WHERE s.program_id = ? AND l.label_name = ?"
            ),
            (program_id, label_name),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown label '{label_name}' in program_id={program_id}")
        return int(row["pc"])

    def step(self, program_id: int, pc: int, env: dict[str, Any]) -> StepResult:
        """Execute exactly one statement for workbench-style stepping."""
        row = self.load_statement(program_id, pc)
        if row is None:
            return StepResult(pc=pc, statement_kind="halt", statement_text="<halt>", output=None, next_pc=None)

        statement_id = int(row["statement_id"])
        kind = str(row["statement_kind"])
        raw_text = str(row["raw_text"])
        next_pc = pc + 1
        output: str | None = None

        if kind == "label":
            pass
        elif kind == "print":
            expr_row = self.connection.execute(
                "SELECT value_expr FROM print_statements WHERE statement_id = ?",
                (statement_id,),
            ).fetchone()
            if expr_row is None:
                raise ValueError(f"Missing print payload for statement_id={statement_id}")
            value_expr = str(expr_row["value_expr"])
            output = str(env.get(value_expr, value_expr))
        elif kind == "set":
            expr_row = self.connection.execute(
                "SELECT var_name, value_expr FROM set_statements WHERE statement_id = ?",
                (statement_id,),
            ).fetchone()
            if expr_row is None:
                raise ValueError(f"Missing set payload for statement_id={statement_id}")
            var_name = str(expr_row["var_name"])
            value_expr = str(expr_row["value_expr"])
            env[var_name] = env.get(value_expr, value_expr)
        elif kind == "goto":
            goto_row = self.connection.execute(
                "SELECT target_label FROM goto_statements WHERE statement_id = ?",
                (statement_id,),
            ).fetchone()
            if goto_row is None:
                raise ValueError(f"Missing goto payload for statement_id={statement_id}")
            next_pc = self._label_to_pc(program_id, str(goto_row["target_label"]))
        elif kind == "if_goto":
            if_row = self.connection.execute(
                "SELECT condition_expr, target_label FROM if_goto_statements WHERE statement_id = ?",
                (statement_id,),
            ).fetchone()
            if if_row is None:
                raise ValueError(f"Missing if_goto payload for statement_id={statement_id}")
            condition_expr = str(if_row["condition_expr"])
            truthy = bool(env.get(condition_expr, False))
            if truthy:
                next_pc = self._label_to_pc(program_id, str(if_row["target_label"]))
        else:
            raise ValueError(f"Unsupported statement_kind: {kind}")

        return StepResult(
            pc=pc,
            statement_kind=kind,
            statement_text=raw_text,
            output=output,
            next_pc=next_pc,
        )

    def find_unreachable_pcs(self, program_id: int, entry_pc: int = 0) -> list[int]:
        """Detect statement positions that cannot be reached from entry_pc."""
        pcs = [
            int(row["pc"])
            for row in self.connection.execute(
                "SELECT pc FROM statements WHERE program_id = ? ORDER BY pc",
                (program_id,),
            )
        ]
        if not pcs:
            return []

        edges: dict[int, set[int]] = {pc: set() for pc in pcs}
        for pc in pcs:
            row = self.load_statement(program_id, pc)
            if row is None:
                continue
            kind = str(row["statement_kind"])
            statement_id = int(row["statement_id"])
            if kind == "goto":
                target = self.connection.execute(
                    "SELECT target_label FROM goto_statements WHERE statement_id = ?",
                    (statement_id,),
                ).fetchone()
                if target is not None:
                    edges[pc].add(self._label_to_pc(program_id, str(target["target_label"])))
            elif kind == "if_goto":
                target = self.connection.execute(
                    "SELECT target_label FROM if_goto_statements WHERE statement_id = ?",
                    (statement_id,),
                ).fetchone()
                if target is not None:
                    edges[pc].add(self._label_to_pc(program_id, str(target["target_label"])))
                if (pc + 1) in edges:
                    edges[pc].add(pc + 1)
            else:
                if (pc + 1) in edges:
                    edges[pc].add(pc + 1)

        visited: set[int] = set()
        stack = [entry_pc]
        while stack:
            current = stack.pop()
            if current in visited or current not in edges:
                continue
            visited.add(current)
            stack.extend(edges[current] - visited)

        return [pc for pc in pcs if pc not in visited]
