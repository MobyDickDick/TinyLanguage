import textwrap

from tiny_language import Debugger, ModuleResolver, Runtime, compile_and_run


def _lines(snapshot_list):
    return [snap.pos.line for snap in snapshot_list]


def test_breakpoint_records_scopes_and_stack():
    program = textwrap.dedent(
        """\
        def x = 1;
        def y = 2;
        print(x + y);
        """
    )

    debugger = Debugger()
    debugger.set_breakpoints(None, {3})

    runtime = Runtime(program)
    runtime.debugger = debugger

    output = compile_and_run(program, runtime=runtime)

    assert output.strip() == "3"
    assert _lines(debugger.snapshots) == [3]

    scope = debugger.snapshots[0].scopes[0]
    assert scope.values["x"] == 1
    assert scope.values["y"] == 2
    assert scope.types["x"] == "number"
    assert scope.types["y"] == "number"
    assert debugger.snapshots[0].call_stack == ()


def test_stepping_sequences_follow_depth_changes():
    program = textwrap.dedent(
        """\
        fn add(a, b) {
            def tmp = a + b;
            return tmp;
        }

        def result = add(2, 3);
        print(result);
        """
    )

    debugger = Debugger()
    debugger.set_breakpoints(None, {6})
    debugger.enqueue_commands("step_in", "step_over", "step_out", "continue")

    runtime = Runtime(program)
    runtime.debugger = debugger

    output = compile_and_run(program, runtime=runtime)

    assert output.strip() == "5"
    assert _lines(debugger.snapshots) == [6, 2, 3, 7]

    inner_scope = debugger.snapshots[2].scopes[0]
    assert inner_scope.values["tmp"] == 5


def test_step_over_skips_imported_module_body(tmp_path):
    helper = tmp_path / "helper.tiny"
    helper.write_text(
        textwrap.dedent(
            """\
            print("helper start");
            print("helper end");
            """
        )
    )

    program = textwrap.dedent(
        """\
        fn runner() {
            import helper as _;
            print("after import");
        }

        def _ = runner();
        """
    )

    debugger = Debugger()
    debugger.set_breakpoints("main", {2})
    debugger.enqueue_commands("step_over", "continue")

    runtime = Runtime(program)
    runtime.debugger = debugger
    resolver = ModuleResolver(search_paths=[tmp_path])

    output = compile_and_run(
        program,
        runtime=runtime,
        module_namespace="main",
        module_resolver=resolver,
    )

    assert "helper start" in output
    assert "helper end" in output
    assert "after import" in output
    assert [snap.namespace for snap in debugger.snapshots] == ["main", "main"]
    assert _lines(debugger.snapshots) == [2, 3]
