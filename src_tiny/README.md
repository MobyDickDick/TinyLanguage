# TinyLanguage demos

This folder collects runnable `.tiny` programs that exercise TinyLanguage
features and runtime behavior.

## Structured concurrency demo

- `structured_concurrency_demo.tiny` shows a `task { ... }` scope that spawns
  work, links it to an `Async.token()`, and cancels the token to stop long
  running tasks. It also demonstrates `join` timeout policies (status-only
  check vs. cancel-on-timeout) and error metadata from failed tasks.
- The demo prints status snapshots using `join(handle, timeout_ms)` and
  `join(handle, timeout_ms, cancel_on_timeout)` so you can see the `JoinStatus`
  metadata (`__tag__`, `done`, `cancelled`, `error`, and `result`) without
  raising exceptions. Task scopes also auto-join with a timeout (configure via
  `TINYLANG_TASK_SCOPE_TIMEOUT_MS`).

Run it from the repo root:

```bash
python -m tiny_language src_tiny/structured_concurrency_demo.tiny
```
