# Structured concurrency design for TinyLanguage

This document outlines a structured concurrency model that extends the existing `spawn`/`join` primitives. The goal is to make asynchronous work predictable, cancellable, and testable without changing the core syntax dramatically.

## Goals

- **Deterministic lifetimes**: Tasks should have a clear owner and terminate before their owner completes.
- **Cancellation tokens**: Cooperative cancellation should propagate to linked tasks and convey a reason string.
- **Safety**: Aborted tasks must not leak partial writes; joins should surface errors consistently.
- **Testing hooks**: Provide helpers that make race-free tests easy to express.

## Proposed model

### Task scopes

- **Task groups**: Introduce an implicit group per block. When a scope exits normally or via error, all linked tasks are joined with a bounded timeout and cancelled if still running.
- **Async functions**: Mark a function as `async fn name(...) { ... }`. Calling an async function returns a handle immediately; `await expr` joins the handle while preserving structured lifetimes.
- **Channels**: Lightweight buffered channels created with `Async.channel(capacity)`. Sends block when full; receives block when empty. Closing a channel wakes receivers with `Null` and sets an `closed` flag.

### Cancellation tokens

- **Creation**: `define token = Async.token();` returns a handle that can be shared.
- **Propagation**: `Async.link(token, handle);` binds an existing `spawn` handle to the token. If the token is already cancelled, the handle is cancelled before running. The link call is idempotent.
- **Observation**: Tasks poll `Async.is_cancelled(token)` inside loops and can look up a reason via `Async.reason(token)` to decide on cleanup steps.
- **Trigger**: `Async.cancel(token, "timeout")` sets the cancellation flag, propagates to linked handles, and returns `true` only on the first call.

### Safe abort paths

- **Cooperative checks**: Long-running loops should poll `Async.is_cancelled` and exit early before mutating shared state.
- **Join semantics**: `join(handle, timeout_ms, cancel_on_timeout)` continues to return a structured status: `{ done, cancelled, error, result }`. Cancelled or errored tasks never populate `result`.
- **Timeouts**: When `cancel_on_timeout` is set, the runtime automatically cancels the handle; callers can still inspect status.

## Testing strategy

- **Deterministic scheduling**: Prefer CPU-bound loops over sleeps so tests are stable on CI. Use `join(handle, 0)` to assert intermediate state without waiting.
- **Cancellation coverage**: Verify that `Async.cancel` prevents shared-state writes and that repeated cancellation calls return `false`.
- **Channel safety**: Tests should cover bounded buffers, closing semantics, and backpressure by mixing send/receive orderings.

## Migration path

1. Ship the `Async` namespace with cancellation tokens (implemented in this change) to unblock cooperative aborts.
2. Add a `task` block construct that groups spawned work and auto-cancels on scope exit.
3. Extend the parser with `async`/`await` syntax while keeping `spawn`/`join` for backwards compatibility.
4. Layer in channel primitives once structured task groups are stable; channels reuse cancellation tokens to abort blocked senders/receivers.
