# Heap usage minimization guidelines

This document defines a lightweight ownership/mutation model plus concrete
patterns for reducing heap allocations in TinyLanguage programs. The intent is
not to forbid heap usage, but to prioritize fixed-size buffers and reuse when
semantics allow it.

## Ownership + mutation model (conventions)

These conventions are intentionally simple and should be followed in code and
examples when minimizing heap use:

1. **Single-owner pointers**: A heap pointer has a single logical owner. When a
   pointer is passed to a helper that mutates it, that helper is considered the
   temporary owner for the duration of the call.
2. **Explicit transfer on return**: If a helper returns a pointer, treat the
   returned pointer as the new owner and avoid mutating the old reference.
3. **No implicit aliasing for mutation**: If two names reference the same heap
   pointer, only one should be used to mutate it. If both need access, treat one
   as read-only and document it in a comment.
4. **Prefer read-only sharing**: Use shared pointers only for read-only access
   (iteration, reporting, formatting). For mutation, pass a pointer explicitly
   to a function that owns the mutation.

These guidelines keep heap aliasing predictable without adding runtime tracking.

## Prefer fixed-size buffers when size is known

If the size is known up front, allocate a fixed-size buffer via `new(size)` and
write into it using `heap_set`:

```tiny
// Prefer a fixed-size buffer and explicit writes.
fn build_pair(a, b) {
    def buf = new(2);
    heap_set(buf, 0, a);
    heap_set(buf, 1, b);
    return buf;
}
```

This minimizes reallocations that would otherwise occur when repeatedly building
`new[...]` literals in loops.

## Reuse buffers in loops

Avoid re-allocating temporary arrays for intermediate results when a reusable
buffer will do:

```tiny
fn sum_pairs(values) {
    def out = new(len(values));
    def idx = 0;
    while (idx < len(values)) {
        def pair = heap_get(values, idx);
        def buf = new(2); // Only if each pair truly needs a unique buffer.
        heap_set(buf, 0, heap_get(pair, 0));
        heap_set(buf, 1, heap_get(pair, 1));
        heap_set(out, idx, buf);
        idx = idx + 1;
    }
    return out;
}
```

When each iteration can share a single scratch buffer, allocate it outside the
loop and reuse it instead of creating a new buffer per iteration.

## Avoid heap literals for transient formatting

When `new[...]` is only used to pass arguments to helpers (e.g., `print` or
`String.join`), prefer small helper functions that take explicit parameters. If
an array is required (e.g., `Python.call` allowlists), reuse an existing shared
allowlist constant rather than rebuilding it.

## Checklist for reviewing heap usage

- [ ] Can this allocation be replaced with `new(size)` + `heap_set`?
- [ ] Is this buffer reused across iterations or rebuilt every time?
- [ ] Are we relying on aliasing without documenting read-only usage?
- [ ] Can scalar variables replace a short-lived array literal?

## Related documentation

- `docs/strict_by_default_safety_profile.md` for strict-mode guidance on
  stack-friendly data structures.
- `docs/python_to_tiny_migration_guide.md` for migration notes that call out
  stack/fixed-size structures.
