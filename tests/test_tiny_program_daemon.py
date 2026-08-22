from pathlib import Path

from tiny_program_daemon import TinyProgramDaemon, TinyProgramGenerator, parse_args
from tiny_program_repository_db_adapter import TinyProgramRepositoryDB


def test_generator_creates_requested_idea_file(tmp_path: Path):
    generator = TinyProgramGenerator(tmp_path, seed=7)

    generated = generator.create_program(slug="nand-gate")

    assert generated.exists()
    assert generated.name.endswith("_nand-gate.tiny")
    content = generated.read_text(encoding="utf-8")
    assert "Auto-generated Tiny program: Boolean NAND gate demo" in content


def test_daemon_run_forever_respects_max_runs(tmp_path: Path):
    generator = TinyProgramGenerator(tmp_path, seed=11)
    daemon = TinyProgramDaemon(generator, interval_seconds=0)

    produced = daemon.run_forever(max_runs=2)

    assert len(produced) == 2
    for path in produced:
        assert path.exists()
        assert path.suffix == ".tiny"


def test_generator_persists_program_to_repository_db(tmp_path: Path):
    db = TinyProgramRepositoryDB(tmp_path / "repo.db")
    db.initialize_schema()
    generator = TinyProgramGenerator(tmp_path, seed=7, repository_db=db)

    generated = generator.create_program(slug="linear-equation")
    source = generated.read_text(encoding="utf-8")
    program_id = db.find_equivalent_program_id(source)

    assert program_id is not None
    db.close()


def test_generator_rejects_duplicate_program_insert(tmp_path: Path):
    db = TinyProgramRepositoryDB(tmp_path / "repo.db")
    db.initialize_schema()
    generator = TinyProgramGenerator(tmp_path, seed=7, repository_db=db)

    generator.create_program(slug="nand-gate")

    try:
        generator.create_program(slug="nand-gate")
    except ValueError as exc:
        assert "already exists in DB" in str(exc)
    else:
        raise AssertionError("Expected duplicate insertion to be rejected")
    db.close()


def test_validator_accepts_loop_with_induction_variable_progress():
    report = TinyProgramGenerator.validate_program(
        """def i = 0;
while (i < 3) {
    if (i == 1) {
        def _unused = print(i);
    }
    i = i + 1;
}
def _unused_result = print(i);
"""
    )

    assert "loop_termination_unproven" not in {issue.code for issue in report.issues}


def test_validator_rejects_loop_without_condition_progress():
    report = TinyProgramGenerator.validate_program(
        """def i = 0;
def total = 0;
while (i < 3) {
    total = total + 1;
}
def _unused_i = print(i);
def _unused_total = print(total);
"""
    )

    assert "loop_termination_unproven" in {issue.code for issue in report.issues}


def test_validator_recognizes_spaced_literal_infinite_loop_once():
    report = TinyProgramGenerator.validate_program("while ( true ) {\n}\n")

    codes = [issue.code for issue in report.issues]
    assert codes.count("infinite_loop_literal") == 1
    assert "loop_termination_unproven" not in codes


def test_validator_accepts_divisor_after_returning_zero_guard():
    report = TinyProgramGenerator.validate_program(
        """fn divide(value, divisor) {
    if (divisor == 0) {
        return null;
    }
    return value / divisor;
}
"""
    )

    assert "division_nonzero_unproven" not in {issue.code for issue in report.issues}


def test_validator_rejects_divisor_without_nonzero_evidence():
    report = TinyProgramGenerator.validate_program(
        """fn divide(value, divisor) {
    return value / divisor;
}
"""
    )

    assert "division_nonzero_unproven" in {issue.code for issue in report.issues}


def test_validator_rejects_reassignment_after_zero_guard():
    report = TinyProgramGenerator.validate_program(
        """fn divide(value, divisor) {
    if (divisor == 0) {
        return null;
    }
    divisor = 0;
    return value / divisor;
}
"""
    )

    codes = [issue.code for issue in report.issues]
    assert codes.count("division_nonzero_unproven") == 1


def test_validator_accepts_statically_bounded_resources():
    report = TinyProgramGenerator.validate_program(
        """def values = new(32);
def i = 0;
while (i < 100) {
    i = i + 1;
}
def _unused_values = print(values);
def _unused_i = print(i);
"""
    )

    codes = {issue.code for issue in report.issues}
    assert "heap_bound_unproven" not in codes
    assert "heap_bound_exceeded" not in codes
    assert "loop_resource_bound_unproven" not in codes
    assert "loop_resource_bound_exceeded" not in codes


def test_validator_rejects_dynamic_heap_allocation():
    report = TinyProgramGenerator.validate_program(
        """fn allocate(size) {
    def values = new(size);
    return values;
}
"""
    )

    assert "heap_bound_unproven" in {issue.code for issue in report.issues}


def test_validator_rejects_excessive_loop_iteration_bound():
    report = TinyProgramGenerator.validate_program(
        """def i = 0;
while (i < 10001) {
    i = i + 1;
}
def _unused_i = print(i);
"""
    )

    assert "loop_resource_bound_exceeded" in {issue.code for issue in report.issues}


def test_validator_rejects_unknown_loop_iteration_bound():
    report = TinyProgramGenerator.validate_program(
        """fn count(limit) {
    def i = 0;
    while (i < limit) {
        i = i + 1;
    }
    return i;
}
"""
    )

    assert "loop_resource_bound_unproven" in {issue.code for issue in report.issues}


def test_deterministic_profile_rejects_time_and_random_sources():
    report = TinyProgramGenerator.validate_program(
        """def roll = Random.randint(1, 6);
def timestamp = Time.now_ms();
def _unused_roll = print(roll);
def _unused_timestamp = print(timestamp);
""",
        deterministic_profile=True,
    )

    assert {issue.code for issue in report.issues} >= {
        "nondeterministic_random_source",
        "nondeterministic_time_source",
    }


def test_deterministic_profile_ignores_comments_strings_and_is_optional():
    source = """// Random.random() is only documentation.
def message = \"Time.now_iso() is only text\";
def _unused_message = print(message);
"""

    strict_report = TinyProgramGenerator.validate_program(
        source, deterministic_profile=True
    )
    default_report = TinyProgramGenerator.validate_program(
        "def value = Random.random();\ndef _unused = print(value);\n"
    )

    assert "nondeterministic_random_source" not in {
        issue.code for issue in strict_report.issues
    }
    assert "nondeterministic_random_source" not in {
        issue.code for issue in default_report.issues
    }


def test_cli_enables_deterministic_profile():
    assert parse_args(["--deterministic"]).deterministic is True


def test_validator_requires_an_explanatory_comment():
    report = TinyProgramGenerator.validate_program(
        'def value = "// not a comment";\ndef _unused = print(value);\n'
    )

    assert "missing_explanatory_comment" in {issue.code for issue in report.issues}


def test_validator_rejects_non_snake_case_declarations():
    report = TinyProgramGenerator.validate_program(
        "// Explain the result.\nfn CalculateValue() { return 1; }\n"
        "def resultValue = CalculateValue();\n"
        "def _unused = print(resultValue);\n"
    )

    issues = {issue.code: issue.message for issue in report.issues}
    assert "non_snake_case_name" in issues
    assert "CalculateValue" in issues["non_snake_case_name"]
    assert "resultValue" in issues["non_snake_case_name"]


def test_validator_applies_category_specific_program_length_limit():
    source = "// Explain the generated program.\n" + "print(1);\n" * 80

    report = TinyProgramGenerator.validate_program(source, category="logic")

    assert "program_too_long" in {issue.code for issue in report.issues}


def test_default_templates_satisfy_style_and_readability_rules(tmp_path: Path):
    generator = TinyProgramGenerator(tmp_path)

    for idea in generator._ideas:
        report = generator.validate_program(idea.template, category=idea.category)
        codes = {issue.code for issue in report.issues}
        assert "missing_explanatory_comment" not in codes
        assert "non_snake_case_name" not in codes
        assert "program_too_long" not in codes
