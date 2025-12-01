# ----- Public API -----

import ast
from typing import List, Optional


def _parse_and_lint(src: str) -> List[IR]:
    parser = Parser(Lexer(src), src)
    stmts = parser.parse()

    lint_import_style(stmts, src)
    lint_destruct_call_outputs(stmts, src)
    lint_no_consecutive_definitions(stmts)
    lint_locals_used(stmts, src)
    lint_unreachable_code(stmts, src)
    signatures = _collect_function_signatures(stmts)

    def lint_nested(block: List[IR]) -> None:
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
) -> str:
    stmts = _parse_and_lint(src)
    runtime = runtime or Runtime(src)  # Reuse an existing runtime or create a fresh one
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

    env = env or Environment(parent=None, namespace=module_namespace)  # Build module environment
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


def run_file(path: str) -> str:
    path_obj = Path(path)  # Accept strings or Path-like objects
    resolved = path_obj.resolve()  # Normalize to an absolute path
    try:
        rel = resolved.relative_to(Path.cwd())  # Try to derive a module namespace from cwd
        namespace = ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001
        namespace = resolved.stem  # Fall back to filename when relative resolution fails
    with open(path, "r", encoding="utf-8") as f:
        return compile_and_run(f.read(), module_namespace=namespace, module_path=resolved)


def _format_error_for_source(source: str, err: TinyLangError) -> str:
    if "(line " in err.message:
        return err.message
    if err.span is not None:
        return format_error(source, err.span, err.message)
    return format_error(source, err.pos, err.message)


def compile_to_python_ast(src: str) -> ast.AST:
    stmts = _parse_and_lint(src)
    return PythonCodeGenerator().module_for_program(stmts)


def compile_to_python_source(src: str) -> str:
    module = compile_to_python_ast(src)
    return PythonCodeGenerator().to_source(module)


def run_with_python_backend(src: str) -> str:
    module = compile_to_python_ast(src)
    namespace: dict = {}
    exec(compile(module, "<tiny_python_backend>", "exec"), namespace, namespace)
    return namespace["tiny_main"]()


def run_with_native_backend(src: str) -> str:
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator().compile_program(stmts)
    return NativeVM().run(program)


def _is_incomplete_source(src: str) -> bool:
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
    if readline is None:
        return  # Nothing to do without readline support
    try:
        readline.write_history_file(history_path)  # Persist the in-memory buffer
    except FileNotFoundError:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.touch()
        readline.write_history_file(history_path)


def _read_repl_command(read_fn) -> Optional[str]:
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
    if isinstance(readline, _FallbackReadline):
        return readline.readline  # Use the fallback implementation when available
    return input  # Otherwise rely on the built-in input()


def main(argv: Optional[List[str]] = None) -> int:
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
    args = parser.parse_args(argv)

    if args.repl and (args.python_backend or args.native_backend):
        parser.error("--native-backend/--python-backend cannot be combined with --repl")

    if args.format_file is not None:
        from formatter import format_source

        with open(args.format_file, "r", encoding="utf-8") as handle:
            print(format_source(handle.read()), end="")
        return 0

    if args.eval is not None:
        try:
            if args.native_backend:
                runner = run_with_native_backend
            elif args.python_backend:
                runner = run_with_python_backend
            else:
                runner = compile_and_run
            output = runner(args.eval)
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
        env = Environment(parent=None, namespace=None)
        runtime = Runtime("")
        scope_provider = lambda: list(KEYWORDS | BUILTINS | set(env.all_names()))
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
                if readline is not None:
                    try:
                        readline.add_history(src)
                    except Exception:
                        pass  # History persistence failures should not crash the REPL
                try:
                    output = compile_and_run(src, env=env, runtime=runtime)
                    if output:
                        print(output, end="")
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

    if args.native_backend:
        output = run_with_native_backend(Path(args.file).read_text(encoding="utf-8"))
    elif args.python_backend:
        output = run_with_python_backend(Path(args.file).read_text(encoding="utf-8"))
    else:
        output = run_file(args.file)
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
