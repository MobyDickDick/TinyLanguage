def test_spawn_results_applied_in_join_order(run_tiny_source):
    out = run_tiny_source(
        """
        fn compute(value) { return value; }

        def counter = new(1);
            def ignored1 = heap_set(counter, 0, 0);

        def first = spawn compute(1);
        def second = spawn compute(2);

        def current = heap_get(counter, 0);
        current = current + join(first);
            def ignored2 = heap_set(counter, 0, current);
        print("after first", heap_get(counter, 0));

        current = heap_get(counter, 0);
        current = current + join(second);
            def ignored3 = heap_set(counter, 0, current);
        print("after second", heap_get(counter, 0));

        print("final", heap_get(counter, 0));
        def _unused = delete(counter);
        """,
    )

    assert out == "after first 1\nafter second 3\nfinal 3\n"


def test_join_waits_for_spawned_heap_update(run_tiny_source):
    out = run_tiny_source(
        """
        fn store(ptr, idx, value) {
            // make sure the indices are read so linting accepts the parameters
            def target = ptr;
            def position = idx;
            def stored = value;
            def ignored1 = heap_set(target, position, stored);
            return stored + heap_get(target, position) - stored;
        }

        def slots = new(2);
        def left = spawn store(slots, 0, 11);
        def right = spawn store(slots, 1, 22);

        print("joined", join(left), join(right));
        print("slots", heap_get(slots, 0), heap_get(slots, 1));
        def _unused = delete(slots);
        """,
    )

    assert out == "joined 11 22\nslots 11 22\n"


def test_join_timeout_status(run_tiny_source):
    out = run_tiny_source(
        """
        fn slow(value) {
            def i = 0;
            while (i < 20000) { i = i + 1; }
            return value;
        }

        def pending = spawn slow(5);

        def first = join(pending, 0);
        print("first", first.done, first.cancelled);

        def final = join(pending);
        print("final", final);
        """,
    )

    assert out == "first false false\nfinal 5\n"


def test_join_timeout_can_cancel(run_tiny_source):
    out = run_tiny_source(
        """
        fn slow(value) {
            def i = 0;
            while (i < 20000) { i = i + 1; }
            return value;
        }

        def first = spawn slow(3);
        def second = spawn slow(7);

        def status_first = join(first, 0);
        print("status", status_first.done, status_first.cancelled);

        def status_second = join(second, 0, true);
        print("cancelled?", status_second.done, status_second.cancelled);

        def first_value = join(first);
        def second_status = join(second, 1000);
        print("final", first_value, second_status.done, second_status.cancelled);
        """,
    )

    assert out == "status false false\ncancelled? false true\nfinal 3 true true\n"


def test_task_block_cancels_pending_spawns(run_tiny_source, monkeypatch):
    monkeypatch.setenv("TINYLANG_TASK_SCOPE_TIMEOUT_MS", "0")
    out = run_tiny_source(
        """
        fn slow(value) {
            def i = 0;
            while (i < 200000) { i = i + 1; }
            return value;
        }

        task {
            def handle = spawn slow(9);
        }

        def status = join(handle, 0);
        print("status", status.done, status.cancelled);
        """,
    )

    assert out == "status false true\n"


def test_task_block_timeout_respects_custom_env(run_tiny_source, monkeypatch):
    monkeypatch.setenv("TINYLANG_TASK_SCOPE_TIMEOUT_MS", "1.5")
    out = run_tiny_source(
        """
        fn slow(value) {
            def i = 0;
            while (i < 2000000) { i = i + 1; }
            return value;
        }

        task {
            def handle = spawn slow(3);
        }

        def status = join(handle, 0);
        print("status", status.done, status.cancelled);
        """,
    )

    assert out == "status false true\n"


def test_task_block_keeps_completed_spawns(run_tiny_source, monkeypatch):
    monkeypatch.setenv("TINYLANG_TASK_SCOPE_TIMEOUT_MS", "50")
    out = run_tiny_source(
        """
        fn quick(value) { return value + 1; }

        def handle = spawn quick(0);
        def _unused = join(handle);
        task {
            handle = spawn quick(4);
        }

        def status = join(handle, 0);
        print("status", status.done, status.cancelled, status.error == Null);
        print("value", join(handle));
        """,
    )

    assert out == "status true false true\nvalue 5\n"


def test_task_block_does_not_cancel_outer_spawns(run_tiny_source, monkeypatch):
    monkeypatch.setenv("TINYLANG_TASK_SCOPE_TIMEOUT_MS", "0")
    out = run_tiny_source(
        """
        fn slow(value, steps) {
            def i = 0;
            while (i < steps) { i = i + 1; }
            return value;
        }

        def outer = spawn slow(1, 20000);

        task {
            def inner = spawn slow(2, 200000);
        }

        def inner_status = join(inner, 0);
        print("inner", inner_status.done, inner_status.cancelled);

        def outer_value = join(outer);
        print("outer", outer_value);
        """,
    )

    assert out == "inner false true\nouter 1\n"


def test_join_status_reports_spawn_errors(run_tiny_source):
    out = run_tiny_source(
        """
        fn boom() {
            return join(Null);
        }

        def handle = spawn boom();
        def status = join(handle, 1000);
        print("status", status.done, status.cancelled);
        print("error", status.error);
        print("result_null", status.result == Null);
        """,
    )

    assert out == (
        "status true false\n"
        "error [E000] join expects a spawn handle (line 3, col 20)\n"
        "   2 |         fn boom() {\n"
        ">  3 |             return join(Null);\n"
        "   4 |         }\n"
        "     |                    ^\n"
        "Stack trace:\n"
        "  at boom (line 2, col 9)\n"
        "result_null true\n"
    )
