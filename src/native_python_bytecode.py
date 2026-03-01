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
    """Return a serialisable view of the program's instruction streams."""

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
heap: Dict[int, List[Any]] = {}
next_ptr = 1
allocations: Dict[int, int] = {}
freed_ptrs: set[int] = set()
freed_allocations: Dict[int, int] = {}
heap_cell_types: Dict[int, Dict[int, str]] = {}
error_message: Any = None


class _MapHelpers:
    @staticmethod
    def new() -> dict[Any, Any]:
        return {}

    @staticmethod
    def set(map_obj: Any, key: Any, value: Any) -> Any:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        map_obj[key] = value
        return map_obj

    @staticmethod
    def get(map_obj: Any, key: Any, default: Any = None) -> Any:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        return map_obj.get(key, default)

    @staticmethod
    def has(map_obj: Any, key: Any) -> bool:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        return key in map_obj

    @staticmethod
    def delete(map_obj: Any, key: Any) -> Any:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        map_obj.pop(key, None)
        return map_obj

    @staticmethod
    def len(map_obj: Any) -> int:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        return len(map_obj)

    @staticmethod
    def keys(map_obj: Any) -> list[Any]:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        return list(map_obj.keys())

    @staticmethod
    def values(map_obj: Any) -> list[Any]:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        return list(map_obj.values())

    @staticmethod
    def entries(map_obj: Any) -> list[list[Any]]:
        if not isinstance(map_obj, dict):
            raise RuntimeError("map operation expects dict")
        return [[k, v] for k, v in map_obj.items()]

    @staticmethod
    def from_entries(entries: Any) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for entry in entries:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                result[entry[0]] = entry[1]
            else:
                raise RuntimeError("Map.from_entries expects [key, value] pairs")
        return result


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


def _record_error(message: str) -> None:
    global error_message
    error_message = message


def _pointer_label(pointer: Any) -> str:
    type_name = type(pointer).__name__
    if isinstance(pointer, (int, float)) and str(pointer).isnumeric():
        return str(int(pointer))
    return f"{pointer!r} ({type_name})"


def _parse_heap_index(index: Any) -> Any:
    try:
        idx = int(index)
    except Exception:
        message = f"heap access error: index {index!r} is not numeric"
        _record_error(message)
        return None
    if isinstance(index, float) and not index.is_integer():
        message = f"heap access error: index {_pointer_label(index)} is not an integer index"
        _record_error(message)
        return None
    return idx


def _resolve_ptr(pointer: Any, op: str) -> Any:
    try:
        ip = int(pointer)
    except Exception:
        message = f"heap {op} error: pointer {_pointer_label(pointer)} is not numeric"
        _record_error(message)
        return None
    if isinstance(pointer, float) and not pointer.is_integer():
        message = f"heap {op} error: pointer {_pointer_label(pointer)} is not an integer pointer"
        _record_error(message)
        return None
    if ip < 1:
        message = f"heap {op} error: pointer {ip} is invalid (must refer to a live positive allocation)"
        _record_error(message)
        return None
    if ip in freed_ptrs:
        size_part = freed_allocations.get(ip)
        size_hint = f" (size {size_part})" if size_part is not None else ""
        message = f"heap {op} error: pointer {ip} was already freed{size_hint}"
        _record_error(message)
        return None
    cells = heap.get(ip)
    if cells is None:
        live = sorted(heap.keys())
        freed = sorted(freed_ptrs)
        details: List[str] = []
        if live:
            details.append(f"live: {live}")
        if freed:
            details.append(f"freed: {freed}")
        context = f" ({'; '.join(details)})" if details else ""
        message = f"heap {op} error: unknown pointer {ip}{context}"
        _record_error(message)
        return None
    return ip, cells


def _heap_new(size: Any) -> int:
    global next_ptr
    count = int(size)
    if count < 0:
        raise RuntimeError("alloc error: negative size")
    ptr = next_ptr
    next_ptr += 1
    heap[ptr] = [0 for _ in range(count)]
    allocations[ptr] = count
    freed_ptrs.discard(ptr)
    freed_allocations.pop(ptr, None)
    heap_cell_types.pop(ptr, None)
    return ptr


def _heap_allocation_size(value: Any) -> int:
    try:
        return int(len(value))
    except Exception:
        return 0


def _value_type_name(value: Any) -> str:
    if isinstance(value, dict) and "__type__" in value:
        return str(value.get("__type__"))
    if value is None:
        return "Null"
    if isinstance(value, bool):
        return "Bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _heap_ok_record() -> Dict[str, Any]:
    return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}


def _heap_error_record(message: str) -> Dict[str, Any]:
    return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": message}}


def _heap_delete(pointer: Any) -> Dict[str, Any]:
    resolved = _resolve_ptr(pointer, "delete")
    if resolved is None:
        return _heap_error_record(error_message or "")
    ip, cells = resolved
    size = allocations.pop(ip, _heap_allocation_size(cells))
    heap.pop(ip, None)
    heap_cell_types.pop(ip, None)
    freed_ptrs.add(ip)
    freed_allocations[ip] = size
    return _heap_ok_record()


def _heap_get(pointer: Any, index: Any) -> Any:
    idx = _parse_heap_index(index)
    if idx is None:
        return None
    resolved = _resolve_ptr(pointer, "access")
    if resolved is None:
        return None
    ip, cells = resolved
    if not isinstance(cells, list):
        message = f"heap access error: pointer {ip} does not refer to a list allocation"
        _record_error(message)
        return None
    size = len(cells)
    if idx < 0 or idx >= size:
        range_hint = "empty allocation" if size == 0 else f"valid indices: 0..{size - 1}"
        message = f"heap access error: index {idx} out of range for pointer {ip} (size {size}; {range_hint})"
        _record_error(message)
        return None
    return cells[idx]


def _heap_set(pointer: Any, index: Any, value: Any) -> Dict[str, Any]:
    idx = _parse_heap_index(index)
    if idx is None:
        return _heap_error_record(error_message or "")
    resolved = _resolve_ptr(pointer, "access")
    if resolved is None:
        return _heap_error_record(error_message or "")
    ip, cells = resolved
    if not isinstance(cells, list):
        message = f"heap access error: pointer {ip} does not refer to a list allocation"
        _record_error(message)
        return _heap_error_record(message)
    size = len(cells)
    if idx < 0 or idx >= size:
        range_hint = "empty allocation" if size == 0 else f"valid indices: 0..{size - 1}"
        message = f"heap access error: index {idx} out of range for pointer {ip} (size {size}; {range_hint})"
        _record_error(message)
        return _heap_error_record(message)
    expected = heap_cell_types.get(ip, {}).get(idx)
    actual = _value_type_name(value)
    if expected is not None and expected != actual:
        message = f"heap type mismatch at {ip}[{idx}]: expected {expected} but got {actual}"
        _record_error(message)
        return _heap_error_record(message)
    cells[idx] = value
    heap_cell_types.setdefault(ip, {})[idx] = actual
    return _heap_ok_record()


def heap_leak_report() -> Dict[str, Any]:
    live = {ptr: _heap_allocation_size(value) for ptr, value in heap.items()}
    leak_count = len(live)
    return {
        "live": live,
        "count": leak_count,
        "total_cells": sum(live.values()),
        "allocations": dict(allocations),
        "freed_sizes": dict(freed_allocations),
        "freed": sorted(freed_ptrs),
        "freed_count": len(freed_ptrs),
        "has_leaks": leak_count > 0,
    }


def _execute(instrs: List, locals_: Dict[str, Any], globals_: Dict[str, Any]) -> Any:
    stack: List[Any] = []
    ip = 0
    while ip < len(instrs):
        op, arg = instrs[ip]
        ip += 1
        if op == "PUSH_CONST":
            stack.append(arg)
        elif op == "LOAD":
            if arg == "errorMessage":
                stack.append(error_message)
            elif arg in locals_:
                stack.append(locals_[arg])
            elif arg in globals_:
                stack.append(globals_[arg])
            else:
                raise RuntimeError(f"unknown variable {arg}")
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
            if name == "__method_call":
                if len(args) < 2:
                    raise RuntimeError(f"__method_call expects at least 2 args, got {len(args)}")
                target = args[0]
                method_name = args[1]
                method_args = args[2:]
                method = getattr(target, method_name, None)
                if method is None:
                    raise RuntimeError(f"attribute {method_name} not found")
                if not callable(method):
                    raise RuntimeError(f"attribute {method_name} is not callable")
                stack.append(method(*method_args))
            elif name in ("__new", "new"):
                if len(args) != 1:
                    raise RuntimeError(f"{name} expects 1 arg, got {len(args)}")
                stack.append(_heap_new(args[0]))
            elif name == "heap_get":
                if len(args) != 2:
                    raise RuntimeError(f"heap_get expects 2 args, got {len(args)}")
                stack.append(_heap_get(args[0], args[1]))
            elif name == "heap_set":
                if len(args) != 3:
                    raise RuntimeError(f"heap_set expects 3 args, got {len(args)}")
                stack.append(_heap_set(args[0], args[1], args[2]))
            elif name == "delete":
                if len(args) != 1:
                    raise RuntimeError(f"delete expects 1 arg, got {len(args)}")
                stack.append(_heap_delete(args[0]))
            else:
                fn = instructions["functions"].get(name)
                if fn is None:
                    raise RuntimeError(f"unknown function {name}")
                if len(args) != len(fn["params"]):
                    raise RuntimeError(f"function {name} expects {len(fn['params'])} args, got {len(args)}")
                locals_child = dict(zip(fn["params"], args))
                stack.append(_execute(fn["instructions"], locals_child, globals_))
        elif op == "POP":
            stack.pop()
        elif op == "RETURN":
            return stack.pop() if stack else None
        else:
            raise RuntimeError(f"unknown opcode {op}")
    return None


def run_program() -> str:
    global_globals: Dict[str, Any] = {"Map": _MapHelpers}
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
