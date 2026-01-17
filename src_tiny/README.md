# TinyLanguage demos

This folder collects runnable `.tiny` programs that exercise TinyLanguage
features and runtime behavior.

## Structured concurrency demo

- `structured_concurrency_demo.tiny` shows a `task { ... }` scope that spawns
  work, links it to an `Async.token()`, and cancels the token to stop long
  running tasks.
- The demo prints status snapshots using `join(handle, timeout_ms)` so you can
  see `done`, `cancelled`, and `error` fields without raising exceptions.

Run it from the repo root:

```bash
python -m tiny_language src_tiny/structured_concurrency_demo.tiny
```
