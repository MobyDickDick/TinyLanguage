# Copy-on-call contract and acceptance

Decision for work package 7, 2026-11-05: **copy mutable arguments independently
of return syntax**. The flag remains opt-in and outside the frozen 1.0 stability
target. This decision replaces the broad escape inference; it does not add a
reference-parameter syntax or change ordinary calls without the flag.

## Identity and mutation

For each Tiny function call, live heap pointers, dictionaries (including
structs, variants and class instances), lists and base views of these objects
are copied before binding. All arguments in that call use the same object and
heap-pointer memos. Repeated references and cycles refer to the corresponding
copies; passing the same object twice produces two parameters sharing one copy.
Immutable leaf values retain their value.

Return expressions never grant mutation permission. A scalar computed from an
argument, a direct alias, a local alias, and a container holding an alias all
follow the same binding rule. Conditional returns do not affect binding, even
when an alias-return branch is never taken. Statements after a guaranteed exit
still fail the existing `E013` unreachable-code check before execution.

Every nested Tiny call establishes another copy boundary. Returning a copy does
not merge its changes into an earlier copy or into caller-owned data. The caller
receives the actual returned value and can explicitly adopt it.

Method-call syntax keeps the receiver shared: `obj.change()` operates on `obj`.
Explicit arguments are copied as for functions. Calling a method on an already
copied parameter operates on that copy. A receiver or base view cannot bypass
protection on an original graph held by an enclosing call, or on an original
also passed as an explicit argument. Existing mutation/return lint requirements
still apply independently of copy-on-call.

While a call is active, field assignment, heap writes, deletion and retagging
through another alias to its original argument graph raise a protected-parameter
error. This includes global aliases and nested calls on the same thread.
Protection ends when the call returns or raises. Returning an alias never
authorizes these writes. Legacy `Fn.return_param_names` and
`MethodDef.return_param_names` fields remain accepted for AST/port compatibility
but have no mutation effect; both parsers now produce empty metadata.

## Executable examples and migration

Scalar calculations preserve the original data. With `--copy-on-call`, this
prints `7` and `1`:

```tiny
fn inspect(buf) {
    def ignored = heap_set(buf, 0, 99);
    def size = len(buf);
    def ignored_copy = delete(buf);
    return size;
}
def data = new[7];
def size = inspect(data);
print(heap_get(data, 0));
print(size);
def ignored_original = delete(data);
```

Previously, `return buf` retained original identity, and even `return len(buf)`
could cause writes to propagate. Under this contract, return the updated data
and receive it explicitly. For a heap buffer, free the old allocation before
rebinding to satisfy the existing single-owner checks. This example prints `7`
before adoption and `99` afterwards:

```tiny
fn bump(buf) {
    def alias = buf;
    def ignored = heap_set(alias, 0, 99);
    return alias;
}
def data = new[7];
def updated = bump(data);
print(heap_get(data, 0));
def ignored_original = delete(data);
data = updated;
print(heap_get(data, 0));
def ignored_updated = delete(data);
```

For objects, assign the returned object where the update should become visible;
preexisting aliases still refer to the old object. Code intentionally requiring
shared function arguments can run without `--copy-on-call` and without
`TINYLANG_COPY_ON_CALL`. There is no per-parameter sharing override. The method
receiver exception is retained from the previous implementation.

## Limits and cost

This is an interpreter argument-binding contract, not a security or purity
guarantee. Builtins, registered native functions, Python interop, closures and
external resources do not acquire isolation by enabling the flag. Protection
uses the existing thread-local call stack; other threads are not locked out.
Other execution backends do not implement this opt-in contract.

Heap pointers retain their numeric representation: values that the runtime
recognizes as live addresses are copied as pointers, including numeric values
equal to such addresses. Distinct numeric and pointer types are not introduced
here. The guarantee covers the supported mutable graph representations above,
not arbitrary host objects. Python recursion depth still limits deeply nested
graphs, even though cycles terminate through memoization.

Copying is eager, not copy-on-write. Time and temporary memo space grow with the
visited graph's distinct nodes and edges. Shared nodes are copied once per call;
nested calls copy again. Heap copies remain manual allocations, with no automatic
collection on return. A callee discarding a heap copy should explicitly delete
it; returned copies become the caller's cleanup responsibility. Deleting a root
does not recursively free its children. This package does not add a collector.

## Reproduction and evidence

Run from the checkout using a development Python with pytest:

```bash
python -m pytest -q tests/detailtests/test_copy_on_call.py tests/test_release_scope_contract.py tests/test_tiny_parser_self_host.py tests/test_language_spec_grammar.py
python benchmarks/copy_on_call.py --sizes 16 64 256 1024 --repeat 7
```

The regression cases derive expected outputs from the contract: the original
stays unchanged, a returned copy contains the mutation, and writes through an
original alias fail. Identity assertions independently check shared/cyclic
lists, maps, class-field storage, heap graphs and mixed object/heap graphs.
CLI flag/environment paths and old externally supplied AST metadata are covered.
Both Tiny examples above execute verbatim in the regression suite.

The [benchmark report](../artifacts/copy-on-call/benchmark.json) records raw
binding times, a separate tracemalloc peak measurement, input sizes, source
hashes, base commit and Python/platform identity. Setup and identity validation
are outside the timed region. Each fresh graph has repeated edges and a cycle;
the object graph also aliases a list across two arguments. The heap graph has
`n + 1` allocations and `3n + 1` cells; enabling copying adds exactly that many,
independent of the duplicate edges. A no-copy binding is measured alongside
each case. Measurements cover parameter binding, not parsing, execution or RSS,
and establish no cross-machine performance budget.

Local Windows CPython 3.12.14 measurements (seven samples per case):

| Graph | Distinct leaves | Copy median (ms) | Traced peak bytes | Added heap allocations |
| --- | ---: | ---: | ---: | ---: |
| Shared/cyclic objects | 16 | 0.119 | 10,487 | 0 |
| Shared/cyclic objects | 1024 | 3.176 | 527,159 | 0 |
| Shared/cyclic heap | 16 | 0.188 | 15,728 | 17 |
| Shared/cyclic heap | 1024 | 11.953 | 979,756 | 1025 |

The measurements show the expected additional cost and bounded copying of
shared nodes. They do not justify a claim that eager copying is inexpensive.

Local regression evidence on 2026-11-05:

- All **61 focused checks** pass in [focused.xml](../artifacts/copy-on-call/focused.xml).
- The [complete run](../artifacts/copy-on-call/full.xml) collects **969 tests**:
  953 pass, seven skip and nine fail. Eight failures are loopback package
  downloads blocked by the network sandbox; the other is the existing
  timing-sensitive `stdlib.time` sleep check (reported elapsed time zero).
- All nine failed cases pass in the [rerun](../artifacts/copy-on-call/rerun.xml)
  with local-network access. Combining the complete run with these replacement
  results gives **962 passing cases and seven skips**, with no remaining failed
  case. This is not an uninterrupted all-green full-suite run, and the timing
  test was not changed by this package.
- Skips cover two Windows symlink-privilege checks, two POSIX executable-mode
  checks, two Linux-only source sandbox checks and optional llvmlite JIT.
  Four existing JUnit warnings concern benchmark `record_property` metadata.
- `python tools/check_format_lint.py` and `git diff --check` pass.

The [checkpoint](../artifacts/copy-on-call/checkpoint.json) binds the retained
reports to their hashes and records maintained source hashes, runner details,
commands and individual rerun/skip cases. This is working-tree evidence, not
release qualification.
