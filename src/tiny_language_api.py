"""Convenience entrypoints for running, compiling, and interacting with TinyLanguage.

This module intentionally collects the most user-facing helpers so external callers
can import a single module when driving the interpreter, native backends, or the
REPL. Functions here prefer descriptive error messages over raw tracebacks and try
to keep a small, ergonomic surface area.
"""

# ----- Public API -----

import ast
import os
import sys
from typing import List, Optional

from native_vm import NativeVM
from native_python_bytecode import run_program_via_python_bytecode
from tiny_language_codegen_llvm import LLVMCodeGenerator
from tiny_language_highlighting import PYGMENTS_AVAILABLE, highlight_source


def _parse_and_lint(src: str) -> List["IR"]:
    """Return a parsed program after running all linter passes.

    The helper centralizes parser creation and the sequence of lints so every entry
    point (REPL, CLI, Python/native backends) benefits from the same validation
    rules. It keeps the order aligned with the standalone linter for predictable
    diagnostics.
    """
    parser = Parser(Lexer(src), src)
    stmts = parser.parse()

    lint_import_style(stmts, src)
    lint_destruct_call_outputs(stmts, src)
    lint_no_consecutive_definitions(stmts)
    lint_assignment_types(stmts, src)
    lint_locals_used(stmts, src)
    lint_unreachable_code(stmts, src)
    signatures = _collect_function_signatures(stmts)

    def lint_nested(block: List["IR"]) -> None:
        for st in block:
            if isinstance(st, Fn):
                lint_fn_params_used(st, src)
            if isinstance(st, MethodDef):
                lint_method_params_used(st, src)
            if isinstance(st, ClassDef):
                for m in st.methods:
                    lint_method_params_used(m, src)
            if isinstance(st, Namespace):
                lint_nested(st.body)

    lint_nested(stmts)
    lint_bare_call_results(stmts, signatures, src)
    return stmts


def compile_and_run(
    src: str,
    env: Optional[Environment] = None,
    runtime: Optional[Runtime] = None,
    *,
    module_namespace: Optional[str] = None,
    module_path: Optional[Path] = None,
    module_resolver: Optional[ModuleResolver] = None,
    debugger: Optional[Debugger] = None,
    stream_output: bool = True,
) -> str:
    """Compile and execute TinyLanguage source, returning concatenated output.

    Parameters mirror the runtime's expectations so callers can opt into
    preconfigured environments, namespace tracking for imports, or custom module
    resolution strategies. Any error raised during execution is intentionally
    allowed to propagate so the caller can render it with full context.
    """
    stmts = _parse_and_lint(src)
    runtime = runtime or Runtime(src)  # Reuse an existing runtime or create a fresh one
    runtime.stream_output = stream_output
    runtime.streamed_output = False
    if debugger is not None:
        runtime.debugger = debugger
    runtime.source_map[module_namespace] = src  # Track source text for later diagnostics
    prev_source = runtime.source  # Remember previous source to restore after module execution
    runtime.source = src  # Swap in the new source for this run
    previous_path = runtime.current_module_path  # Save module bookkeeping fields
    previous_namespace = runtime.current_module_namespace
    runtime.current_module_path = module_path
    runtime.current_module_namespace = module_namespace
    if module_resolver is not None:
        runtime.module_resolver = module_resolver  # Override resolver when running imports
    runtime.output.clear()  # Reset buffered program output
    runtime.error_messages.clear()  # Reset accumulated error messages

    env = env or Environment(parent=None, namespace=module_namespace, runtime=runtime)  # Build module environment
    if module_namespace:
        runtime.namespace_envs[module_namespace] = env  # Register namespace for imports
    runtime.global_env = env  # Keep a reference for the runtime
    register_stdlib(runtime, env, NamespaceRef)  # Expose built-in functions and types
    try:
        for st in stmts:
            runtime.eval_stmt(st, env, namespace=module_namespace)  # Evaluate each top-level stmt
    finally:
        runtime.current_module_path = previous_path  # Restore runtime context even on errors
        runtime.current_module_namespace = previous_namespace
        runtime.source = prev_source
    return "".join(runtime.output)


def run_file(path: str, *, stream_output: bool = True) -> str:
    """Execute a TinyLanguage source file and return its printed output."""
    path_obj = Path(path)  # Accept strings or Path-like objects
    resolved = path_obj.resolve()  # Normalize to an absolute path
    try:
        rel = resolved.relative_to(Path.cwd())  # Try to derive a module namespace from cwd
        namespace = ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001
        namespace = resolved.stem  # Fall back to filename when relative resolution fails
    runtime = Runtime(path_obj.read_text(encoding="utf-8"))
    with open(path, "r", encoding="utf-8") as f:
        output = compile_and_run(
            f.read(),
            runtime=runtime,
            module_namespace=namespace,
            module_path=resolved,
            stream_output=stream_output,
        )
    if stream_output and not runtime.streamed_output:
        print(output, end="")
    return output


def _format_error_for_source(source: str, err: TinyLangError) -> str:
    """Format an error with source context when available."""
    if "(line " in err.message:
        return err.message
    location = err.span if err.span is not None else err.pos
    return format_error(source, location, err.message, code=err.code, hint=err.hint)


def compile_to_python_ast(src: str) -> ast.AST:
    """Translate TinyLanguage code into an equivalent Python ``ast.AST`` module."""
    stmts = _parse_and_lint(src)
    return PythonCodeGenerator().module_for_program(stmts)


def compile_to_python_source(src: str) -> str:
    """Compile TinyLanguage code into runnable Python source text."""
    module = compile_to_python_ast(src)
    return PythonCodeGenerator().to_source(module)


def compile_to_llvm_ir(src: str) -> str:
    """Emit textual LLVM IR for the subset supported by the native backend."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator().compile_program(stmts)
    return LLVMCodeGenerator().compile_program(program)


def run_with_python_backend(src: str) -> str:
    """Execute TinyLanguage code by generating and running Python source."""
    module = compile_to_python_ast(src)
    namespace: dict = {}
    exec(compile(module, "<tiny_python_backend>", "exec"), namespace, namespace)
    return namespace["tiny_main"]()


def run_with_native_backend(src: str) -> str:
    """Run code through the experimental native bytecode backend and VM."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator().compile_program(stmts)
    return NativeVM().run(program)


def run_with_python_bytecode_backend(src: str) -> str:
    """Execute native IR by emitting Python bytecode instructions."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator().compile_program(stmts)
    return run_program_via_python_bytecode(program)


def _is_incomplete_source(src: str) -> bool:
    """Return True when the REPL buffer still has unclosed delimiters or strings."""
    balances = {"(": 0, "[": 0, "{": 0}
    in_string = False
    escape = False
    for ch in src:
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in balances:
            balances[ch] += 1
        elif ch in (")", "]", "}"):
            match = {"}": "{", ")": "(", "]": "["}[ch]
            if balances[match] > 0:
                balances[match] -= 1
    return in_string or any(v > 0 for v in balances.values())


def _configure_readline(
    history_path: Path, scope_provider: Callable[[], List[str]] = lambda: sorted(KEYWORDS | BUILTINS)
) -> None:
    """Wire tab completion and history persistence for the REPL when available."""
    if readline is None:
        return  # Skip configuration if readline support is unavailable
    readline.set_completer_delims(" \t\n")  # Treat whitespace as completion delimiters

    def completer(text: str, state: int) -> Optional[str]:
        completions = sorted(set(scope_provider()))  # Grab the latest symbol list
        matches = [word for word in completions if word.startswith(text)]
        return matches[state] if state < len(matches) else None  # Return nth match or None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")  # Enable tab completion binding
    try:
        readline.read_history_file(history_path)  # Load persisted history if available
    except FileNotFoundError:
        history_path.touch()  # Create an empty history file on first run
    readline.set_history_length(1000)  # Keep a generous but bounded history size


def _save_history(history_path: Path) -> None:
    """Persist REPL history to disk when readline support exists."""
    if readline is None:
        return  # Nothing to do without readline support
    try:
        readline.write_history_file(history_path)  # Persist the in-memory buffer
    except FileNotFoundError:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.touch()
        readline.write_history_file(history_path)


def _read_repl_command(read_fn) -> Optional[str]:
    """Read a single REPL submission, allowing multiline input when needed."""
    buffer: List[str] = []  # Accumulate multi-line input until braces balance
    while True:
        prompt = "tiny> " if not buffer else "...> "  # Primary or continuation prompt
        try:
            line = read_fn(prompt)  # Ask the configured read function for input
        except EOFError:
            return None if not buffer else "\n".join(buffer)  # Exit or return partial block
        buffer.append(line)
        src = "\n".join(buffer)
        if _is_incomplete_source(src):
            continue  # Keep reading if brackets/parens are unbalanced
        return src


def _resolve_read_fn():
    """Choose the appropriate input function depending on readline availability."""
    if isinstance(readline, _FallbackReadline):
        return readline.readline  # Use the fallback implementation when available
    return input  # Otherwise rely on the built-in input()


def _repl_highlighting_enabled() -> bool:
    """Return True when REPL syntax highlighting should be active."""

    if not PYGMENTS_AVAILABLE:
        return False  # Skip when pygments is not installed

    env_flag = os.environ.get("TINYL_REPL_HIGHLIGHT", "").strip().lower()
    if env_flag in {"0", "false", "off", "no"}:
        return False  # Opt-out when users request it explicitly

    return sys.stdout.isatty()  # Only highlight when writing to an interactive TTY


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for running files, snippets, REPL sessions, or codegen."""
    parser = argparse.ArgumentParser(description="Run a TinyLanguage program from a file")
    mode_group = parser.add_mutually_exclusive_group()  # Eval and REPL are exclusive options
    mode_group.add_argument(
        "-e",
        "--eval",
        metavar="SRC",
        help="Execute the provided TinyLanguage source code string",
    )
    mode_group.add_argument("--repl", action="store_true", help="Start a TinyLanguage REPL")
    mode_group.add_argument(
        "--format",
        dest="format_file",
        metavar="FILE",
        help="Format the given TinyLanguage source file and print the result",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the TinyLanguage source file to execute",
    )
    parser.add_argument(
        "--emit-python",
        dest="emit_python",
        metavar="FILE",
        help="Emit Python code generated from TinyLanguage and write it to FILE (use '-' for stdout)",
    )
    backend_group = parser.add_mutually_exclusive_group()
    backend_group.add_argument(
        "--python-backend",
        action="store_true",
        help="Execute the program via the experimental Python codegen backend",
    )
    backend_group.add_argument(
        "--native-backend",
        action="store_true",
        help="Execute the program via the experimental native bytecode backend",
    )
    backend_group.add_argument(
        "--native-python-bytecode",
        action="store_true",
        help="Execute the program by compiling native IR to pure Python bytecode",
    )
    args = parser.parse_args(argv)

    if args.repl and (args.python_backend or args.native_backend or args.native_python_bytecode):
        parser.error("--native-backend/--python-backend cannot be combined with --repl")

    if args.format_file is not None:
        from formatter import format_source

        with open(args.format_file, "r", encoding="utf-8") as handle:
            print(format_source(handle.read()), end="")
        return 0

    if args.eval is not None:
        try:
            streamed = False
            if args.native_backend:
                output = run_with_native_backend(args.eval)
            elif args.native_python_bytecode:
                output = run_with_python_bytecode_backend(args.eval)
            elif args.python_backend:
                output = run_with_python_backend(args.eval)
            else:
                runtime = Runtime(args.eval)
                output = compile_and_run(args.eval, runtime=runtime, stream_output=True)
                streamed = runtime.streamed_output

            if not streamed:
                print(output, end="")
            return 0
        except TinyLangError as err:
            print(_format_error_for_source(args.eval, err), file=sys.stderr)
            return 1
        except Exception as exc:  # pragma: no cover - unexpected errors
            print(str(exc), file=sys.stderr)
            return 1

    if args.repl:  # Interactive shell mode
        history_path = Path.home() / ".tiny_language_history"
        runtime = Runtime("")
        env = Environment(parent=None, namespace=None, runtime=runtime)
        scope_provider = lambda: list(KEYWORDS | BUILTINS | set(env.all_names()))
        highlight_enabled = _repl_highlighting_enabled()
        _configure_readline(history_path, scope_provider)
        read_fn = _resolve_read_fn()
        try:
            while True:
                src = _read_repl_command(read_fn)
                if src is None:
                    print()
                    break
                if not src.strip():
                    continue  # Ignore blank submissions
                if highlight_enabled:
                    highlighted = highlight_source(src)
                    if highlighted:
                        print(highlighted, end="" if highlighted.endswith("\n") else "\n")
                if readline is not None:
                    try:
                        readline.add_history(src)
                    except Exception:
                        pass  # History persistence failures should not crash the REPL
                try:
                    compile_and_run(src, env=env, runtime=runtime, stream_output=True)
                except TinyLangError as err:
                    print(_format_error_for_source(src, err), file=sys.stderr)
                except Exception as exc:  # pragma: no cover - unexpected errors
                    print(str(exc), file=sys.stderr)
        finally:
            _save_history(history_path)  # Always attempt to save history on exit
        return 0

    if args.emit_python:
        if not args.file:
            parser.error("--emit-python requires a source file")
        source_text = Path(args.file).read_text(encoding="utf-8")
        generated = compile_to_python_source(source_text)
        if args.emit_python == "-":
            print(generated)
        else:
            Path(args.emit_python).write_text(generated, encoding="utf-8")
        return 0

    if not args.file:
        parser.error("the following arguments are required: file")  # Align with argparse behavior

    streamed = False
    if args.native_backend:
        output = run_with_native_backend(Path(args.file).read_text(encoding="utf-8"))
    elif args.python_backend:
        output = run_with_python_backend(Path(args.file).read_text(encoding="utf-8"))
    else:
        output = run_file(args.file, stream_output=True)
        streamed = True

    if not streamed:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "compile_and_run",
    "compile_to_python_ast",
    "compile_to_python_source",
    "run_with_python_backend",
    "run_with_native_backend",
    "run_file",
    "main",
    "ModuleResolver",
]
