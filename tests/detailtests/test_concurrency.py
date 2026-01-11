def test_spawn_results_applied_in_join_order(run_tiny_source):
    out = run_tiny_source(
        """
        fn compute(value) { return value; }

        def counter = new(1);
            def _ = heap_set(counter, 0, 0);

        def first = spawn compute(1);
        def second = spawn compute(2);

        def current = heap_get(counter, 0);
        current = current + join(first);
            def _ = heap_set(counter, 0, current);
        print("after first", heap_get(counter, 0));

        current = heap_get(counter, 0);
        current = current + join(second);
            def _ = heap_set(counter, 0, current);
        print("after second", heap_get(counter, 0));

        print("final", heap_get(counter, 0));
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
            def _ = heap_set(target, position, stored);
            return stored + heap_get(target, position) - stored;
        }

        def slots = new(2);
        def left = spawn store(slots, 0, 11);
        def right = spawn store(slots, 1, 22);

        print("joined", join(left), join(right));
        print("slots", heap_get(slots, 0), heap_get(slots, 1));
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
