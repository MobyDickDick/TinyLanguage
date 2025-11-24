def test_spawn_results_applied_in_join_order(run_tiny_source):
    out = run_tiny_source(
        """
        fn compute(value) { return value; }

        define counter = new(1);
        heap_set(counter, 0, 0);

        define first = spawn compute(1);
        define second = spawn compute(2);

        define current = heap_get(counter, 0);
        current = current + join(first);
        heap_set(counter, 0, current);
        print("after first", heap_get(counter, 0));

        current = heap_get(counter, 0);
        current = current + join(second);
        heap_set(counter, 0, current);
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
            define target = ptr;
            define position = idx;
            define stored = value;
            heap_set(target, position, stored);
            return stored + heap_get(target, position) - stored;
        }

        define slots = new(2);
        define left = spawn store(slots, 0, 11);
        define right = spawn store(slots, 1, 22);

        print("joined", join(left), join(right));
        print("slots", heap_get(slots, 0), heap_get(slots, 1));
        """,
    )

    assert out == "joined 11 22\nslots 11 22\n"
