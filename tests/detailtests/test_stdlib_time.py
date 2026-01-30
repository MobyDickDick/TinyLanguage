"""Tests for the stdlib time module."""

from __future__ import annotations

from tests.detailtests.stdlib_helpers import stdlib_program


def test_stdlib_time_now_and_sleep(run_tiny_source, monkeypatch):
    """Validate time helpers return monotonic values and ISO timestamps."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")

    sleep_ms = 10
    out = run_tiny_source(
        stdlib_program(
            "time",
            f"""
            def t1 = time.now_ms();
            def m1 = time.monotonic_ms();
            def elapsed = time.sleep_ms({sleep_ms});
            def t2 = time.now_ms();
            def m2 = time.monotonic_ms();
            def iso = time.now_iso();

            print(t1);
            print(t2);
            print(m1);
            print(m2);
            print(elapsed);
            print(iso);
            """,
        ),
    )

    lines = out.strip().splitlines()
    assert len(lines) == 6

    t1 = float(lines[0])
    t2 = float(lines[1])
    m1 = float(lines[2])
    m2 = float(lines[3])
    elapsed = float(lines[4])
    iso = lines[5]

    assert t2 >= t1
    assert m2 >= m1
    assert elapsed >= sleep_ms
    assert iso.endswith("Z")
    assert "T" in iso
