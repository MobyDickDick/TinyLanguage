# Fuzzing TinyLanguage programs

TinyLanguage includes a small set of property-based fuzz tests to catch lexer, parser, and runtime crashes early. The tests live in [`tests/detailtests/test_benchmark_and_fuzz.py`](../tests/detailtests/test_benchmark_and_fuzz.py) and are optional by design so they can be enabled locally without slowing down every CI run.

## Prerequisites

- Install [Hypothesis](https://hypothesis.readthedocs.io/) to unlock the property-based tests:

  ```bash
  pip install hypothesis
  ```

- The rest of the test suite only depends on the standard `pytest` tooling already in `requirements`.

## Running the fuzz tests

- Quick smoke test that uses a handful of pre-generated seeds for runtime, lexer, and parser fuzzing:

  ```bash
  python -m pytest tests/detailtests/test_benchmark_and_fuzz.py -k randomized_programs_do_not_crash
  ```

- Property-based fuzzing with shrinking (requires Hypothesis):

  ```bash
  python -m pytest tests/detailtests/test_benchmark_and_fuzz.py -k "shrink_on_failure or round_trip_matches_python or generated_statements_execute or match_python_reference or lexer_handles_random_text or parser_handles_random_text"
  ```

  These tests generate arithmetic and control-flow snippets, run them through `compile_and_run`, and rely on Hypothesis to shrink any failing seed.
  The `match_python_reference` case additionally builds small programs with definitions, assignments, and `print` statements,
  executes them both in TinyLanguage and a tiny Python reference evaluator, and checks that every emitted line matches.
  The lexer/parser fuzz cases generate random text inputs to ensure we consistently surface `TinyLangError` instead of crashing.

## Nightly runs

- CI runs the fuzz suite nightly via the scheduled GitHub Actions workflow in
  `.github/workflows/nightly-fuzz.yml`. Use `workflow_dispatch` to trigger it
  manually if you need coverage outside the schedule.

## Tips

- If a generated program times out, re-run the test with the recorded seed to reproduce locally and adjust `_run_program_with_timeout` in the test if your machine is unusually slow.
- The fuzz helper functions `_generate_program`, `_printable_exprs`, and `_tiny_programs` can be extended with new constructs to cover additional language features.
