import textwrap

from tiny_language import Debugger, Runtime, compile_and_run


def _lines(snapshot_list):
    return [snap.pos.line for snap in snapshot_list]


def test_breakpoint_records_scopes_and_stack():
    program = textwrap.dedent(
        """\
        define x = 1;
        define y = 2;
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
            define tmp = a + b;
            return tmp;
        }

        define result = add(2, 3);
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


def test_debugger_resets_stale_pause_flags():
    program = textwrap.dedent(
        """\
        define n = 1;
        print(n);
        """
    )

    runtime = Runtime(program)
    debugger = Debugger()
    debugger.force_pause = True  # Simulate a left-over pause request from a prior session
    runtime.debugger = debugger

    output = compile_and_run(program, runtime=runtime)

    assert output.strip() == "1"
    assert debugger.snapshots == []
    assert debugger.pending_step is None
    assert debugger.last_location is None
    assert debugger.force_pause is False
