import textwrap


def test_async_functions_can_be_awaited(run_tiny_source):
    out = run_tiny_source(
        textwrap.dedent(
            """
            async fn compute(x) { return x + 2; }

            define res = await compute(5);
            print("res", res);

            define first = compute(1);
            define second = compute(2);
            print("order", await second, await first);
            """
        )
    )

    assert out == "res 7\norder 4 3\n"


def test_channels_block_and_close_cleanly(run_tiny_source):
    out = run_tiny_source(
        textwrap.dedent(
            """
            fn push(chan, value) { return Async.send(chan, value); }

            define chan = Async.channel(1);
            define sent_first = Async.send(chan, 1);
            define pushing = spawn push(chan, 2);

            define status_pending = join(pushing, 0, false);
            print("pending", status_pending.done, status_pending.cancelled);

            define first = Async.recv(chan);
            define status_done = join(pushing, 1000, false);
            define second = Async.recv(chan);

            define closed_once = Async.close(chan);
            define closed_twice = Async.close(chan);
            define drained = Async.recv(chan);

            print("results", sent_first, first, second, status_done.done, closed_once, closed_twice, drained == Null);
            """
        )
    )

    assert out == "pending false false\nresults true 1 2 true true false true\n"
