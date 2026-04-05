# TinyLanguage demos

This folder collects runnable `.tiny` programs that exercise TinyLanguage
features and runtime behavior.

## Structured concurrency demo

- `structured_concurrency_demo.tiny` shows a `task { ... }` scope that spawns
  work, links it to an `Async.token()`, and cancels the token to stop long
  running tasks. It also demonstrates `join` timeout policies (status-only
  check vs. cancel-on-timeout), a full `join(handle)` for a completed result,
  and error metadata from failed tasks, plus cancellation reasons surfaced via
  `Async.reason` inside workers. It shows that `Async.link` is idempotent and
  that linking after cancellation returns `false`. It also shows manual handle
  cancellation via `cancel(handle)`, exercises the `Async.channel` send/recv
  helpers (including idempotent channel closing), and shows `async fn` +
  `await` alongside `spawn`/`join`.
  The demo also leaves one long-running handle unlinked so the task scope
  auto-join path (which tracks all spawned handles, linked or not) can cancel
  it on timeout.
- The demo prints status snapshots using `join(handle, timeout_ms)` and
  `join(handle, timeout_ms, cancel_on_timeout)` so you can see the `JoinStatus`
  metadata (`__tag__`, `done`, `cancelled`, `error`, and `result`) without
  raising exceptions. It also prints the boolean results from `Async.link` and
  shows the cancellation reason via `Async.reason`. Task scopes auto-join with
  a timeout (configure via `TINYLANG_TASK_SCOPE_TIMEOUT_MS`).

Run it from the repo root:

```bash
python -m tiny_language src_tiny/structured_concurrency_demo.tiny
```

## GUI demo

- `gui_hello_app.tiny` shows a tiny desktop app built with `import stdlib.gui;`.
  The module uses a declarative app map (`gui.app`, `gui.label`, `gui.button`)
  and launches a Tkinter window via `gui.run(...)`.

Run it from the repo root:

```bash
python -m tiny_language src_tiny/gui_hello_app.tiny
```
