import textwrap


def test_cancellation_token_stops_linked_spawn(run_tiny_source):
    out = run_tiny_source(
        textwrap.dedent(
            """
            fn worker(token, ptr) {
                def i = 0;
                while (i < 50000) {
                    if (Async.is_cancelled(token)) { return "cancelled"; }
                    i = i + 1;
                }
                heap_set(ptr, 0, 1);
                return "done";
            }

            def token = Async.token();
            def ptr = new(1);
            heap_set(ptr, 0, 0);

            def handle = spawn worker(token, ptr);
            def linked = Async.link(token, handle);
            def cancelled = Async.cancel(token, "stop");

            def status = join(handle, 1000);
            print("status", status.done, status.cancelled, status.error != Null, linked, cancelled);
            print("reason", Async.reason(token));
            print("writes", heap_get(ptr, 0));
            """
        )
    )

    assert out == "status true true true true true\nreason stop\nwrites 0\n"


def test_cancellation_token_idempotent_and_immediate(run_tiny_source):
    out = run_tiny_source(
        textwrap.dedent(
            """
            fn quick(token) {
                if (Async.is_cancelled(token)) { return "blocked"; }
                return "live";
            }

            def token = Async.token();
            def handle = spawn quick(token);
            def linked = Async.link(token, handle);

            def first = Async.cancel(token, "first");
            def second = Async.cancel(token, "second");

            def status = join(handle, 1000);

            def late = spawn quick(token);
            def late_linked = Async.link(token, late);
            def late_status = join(late, 1000);

            print("first", first, "second", second, linked);
            print("cancelled", status.cancelled, Async.is_cancelled(token), Async.reason(token));
            print("late", late_status.cancelled, late_linked);
            """
        )
    )

    assert out == "first true second false true\ncancelled true true first\nlate true false\n"
