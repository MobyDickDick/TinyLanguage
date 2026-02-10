# TinyLanguage debugger trace guide (async tasks)

This guide captures a worked trace for async task scheduling and stepping.
It complements `docs/debugger_workflows.md` (VS Code/DAP) with a CLI-first
trace transcript that is easy to diff in reviews.

## Goal

Show what `tiny debug trace` should print when multiple async tasks are
scheduled and awaited.

## Example program

Create `examples/debug/async_trace_demo.tiny` with:

```tiny
async fn compute(x) {
    def doubled = x + x;
    return doubled;
}

async fn orchestrate() {
    def a = spawn compute(3);
    def b = spawn compute(7);
    def left = await a;
    def right = await b;
    return left + right;
}

def total = await orchestrate();
print(total);
```

## Trace command

```bash
tiny debug trace examples/debug/async_trace_demo.tiny \
  --breakpoint 3 \
  --breakpoint 8 \
  --breakpoint 9 \
  --breakpoint 10
```

## Expected trace output

```text
[trace] start module=main
[trace] breakpoint line=3 fn=compute task=task-1 locals={x: 3, doubled: 6}
[trace] breakpoint line=8 fn=orchestrate task=main locals={a: <spawn-handle task-1 done>}
[trace] breakpoint line=3 fn=compute task=task-2 locals={x: 7, doubled: 14}
[trace] breakpoint line=9 fn=orchestrate task=main locals={a: <spawn-handle task-1 done>, b: <spawn-handle task-2 done>}
[trace] breakpoint line=10 fn=orchestrate task=main locals={a: <spawn-handle task-1 done>, b: <spawn-handle task-2 done>, left: 6}
[trace] stdout: 20
[trace] end status=ok
```

## How to read this transcript

- Two `compute` tasks are scheduled (`task-1`, `task-2`) and each hits line 3.
- Control returns to `orchestrate` where `a` and `b` are visible as finished
  spawn handles before the `await` points complete.
- The final stdout value (`20`) confirms both awaited results were combined.

## Notes for regressions

When this workflow fails, capture and attach:

1. The full `tiny debug trace ...` command line.
2. The trace log output.
3. The Tiny source file used for the run.
4. Backend/runtime flags (if any) used during the trace session.
