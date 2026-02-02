# stdlib.random parity map

This parity map enumerates the subset of Python's `random` module that
TinyLanguage mirrors today. Each entry lists the Python API and the
corresponding TinyLanguage function exposed by `stdlib.random`.

## Core functions

| Python `random` | TinyLanguage `stdlib.random` | Notes |
| --- | --- | --- |
| `random.random()` | `random.random()` | Uniform float in the range `[0.0, 1.0)`. |
| `random.randint(a, b)` | `random.randint(a, b)` | Inclusive integer range. |
| `random.choice(seq)` | `random.choice(seq)` | Expects an indexable sequence. |
| `random.shuffle(seq)` | `random.shuffle(seq)` | Shuffles in place; returns the sequence. |
| `random.seed(value)` | `random.seed(value)` | Seeds the RNG for deterministic output. |

## Parity coverage notes

- Deterministic parity tests use fixed seeds to compare TinyLanguage outputs to
  Python `random` results in `tests/test_stdlib_compatibility.py`.
