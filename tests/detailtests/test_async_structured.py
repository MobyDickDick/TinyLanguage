"""Structured async execution tests for TinyLanguage."""

import textwrap


def test_async_functions_can_be_awaited(run_tiny_source):
    """Ensure async functions return values that can be awaited in order."""
    out = run_tiny_source(
        textwrap.dedent(
            """
            async fn compute(x) { return x + 2; }

            def res = await compute(5);
            print("res", res);

            def first = compute(1);
            def second = compute(2);
            print("order", await second, await first);
            """
        )
    )

    assert out == "res 7\norder 4 3\n"


def test_channels_block_and_close_cleanly(run_tiny_source):
    """Validate channel send/recv semantics, blocking, and closing behavior."""
    out = run_tiny_source(
        textwrap.dedent(
            """
            fn push(chan, value) { return Async.send(chan, value); }

            def chan = Async.channel(1);
            def sent_first = Async.send(chan, 1);
            def pushing = spawn push(chan, 2);

            def status_pending = join(pushing, 0, false);
            print("pending", status_pending.done, status_pending.cancelled);

            def first = Async.recv(chan);
            def status_done = join(pushing, 1000, false);
            def second = Async.recv(chan);

            def closed_once = Async.close(chan);
            def closed_twice = Async.close(chan);
            def drained = Async.recv(chan);

            print("results", sent_first, first, second, status_done.done, closed_once, closed_twice, drained == Null);
            """
        )
    )

    assert out == "pending false false\nresults true 1 2 true true false true\n"
