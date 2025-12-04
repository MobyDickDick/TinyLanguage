"""Experimental Python bytecode emitter for the native IR.

The module takes the native ``ProgramIR`` produced by
``NativeCodeGenerator`` and translates it into a tiny Python function
that mirrors the stack-based VM. The generated function is compiled to
Python bytecode via ``compile``/``exec`` so callers can exercise a
"pure Python" execution path without going through the hand-written
``NativeVM`` loop.
"""

from __future__ import annotations

from typing import Dict, List

from native_ir import ProgramIR


def _format_instructions(program: ProgramIR) -> Dict[str, List[tuple]]:
    return {
        "entry": [(instr.op.value, instr.arg) for instr in program.entry],
        "functions": {
            name: {
                "params": fn.params,
                "instructions": [(instr.op.value, instr.arg) for instr in fn.instructions],
            }
            for name, fn in program.functions.items()
        },
    }


def generate_python_source(program: ProgramIR) -> str:
    """Return Python source that executes the given ``ProgramIR``.

    The emitted code embeds instructions as literals and performs the
    same stack/dispatch logic as ``NativeVM``. ``print`` statements are
    captured in ``output`` so the caller receives the combined string.
    """

    state = _format_instructions(program)
    template = '''
from typing import Any, Dict, List

instructions = {state}


def _binary(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right
    if op == "%":
        return left % right
    if op == "^":
        return left ** right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    if op in ("&&", "and"):
        return bool(left) and bool(right)
    if op in ("||", "or"):
        return bool(left) or bool(right)
    raise RuntimeError(f"unsupported operator {{op}}")


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _execute(instrs: List, locals_: Dict[str, Any], globals_: Dict[str, Any]) -> Any:
    stack: List[Any] = []
    ip = 0
    while ip < len(instrs):
        op, arg = instrs[ip]
        ip += 1
        if op == "PUSH_CONST":
            stack.append(arg)
        elif op == "LOAD":
            if arg in locals_:
                stack.append(locals_[arg])
            elif arg in globals_:
                stack.append(globals_[arg])
            else:
                raise RuntimeError(f"unknown variable {{arg}}")
        elif op == "STORE":
            value = stack.pop()
            locals_[arg] = value
            if locals_ is globals_:
                globals_[arg] = value
        elif op == "BINARY":
            right = stack.pop()
            left = stack.pop()
            stack.append(_binary(arg, left, right))
        elif op == "PRINT":
            values = [stack.pop() for _ in range(int(arg))][::-1]
            output.append(" ".join(_format_value(v) for v in values) + "\\n")
        elif op == "JUMP":
            ip = int(arg)
        elif op == "JUMP_IF_FALSE":
            cond = stack.pop()
            if not cond:
                ip = int(arg)
        elif op == "CALL":
            name, argc = arg
            args = [stack.pop() for _ in range(argc)][::-1]
            fn = instructions["functions"].get(name)
            if fn is None:
                raise RuntimeError(f"unknown function {{name}}")
            if len(args) != len(fn["params"]):
                raise RuntimeError(f"function {{name}} expects {{len(fn['params'])}} args, got {{len(args)}}")
            locals_child = dict(zip(fn["params"], args))
            stack.append(_execute(fn["instructions"], locals_child, globals_))
        elif op == "POP":
            stack.pop()
        elif op == "RETURN":
            return stack.pop() if stack else None
        else:
            raise RuntimeError(f"unknown opcode {{op}}")
    return None


def run_program() -> str:
    global_globals: Dict[str, Any] = {}
    _execute(instructions["entry"], global_globals, global_globals)
    return "".join(output)


output: List[str] = []
RESULT = run_program()
'''

    return template.replace("{state}", repr(state))


def compile_python_bytecode(program: ProgramIR):
    """Compile the program to a Python code object.

    The returned object can be executed with ``exec`` to obtain the
    ``RESULT`` variable containing the concatenated output.
    """

    source = generate_python_source(program)
    return compile(source, "<native_python_bytecode>", "exec")


def run_program_via_python_bytecode(program: ProgramIR) -> str:
    code_obj = compile_python_bytecode(program)
    namespace: Dict[str, object] = {}
    exec(code_obj, namespace, namespace)
    result = namespace.get("RESULT")
    return "" if result is None else str(result)
