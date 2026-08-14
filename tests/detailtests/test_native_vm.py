"""Unit tests for the low-level native virtual machine."""

from native_ir import FunctionIR, Instruction, Opcode, ProgramIR
from native_vm import NativeVM


def test_vm_runs_simple_program():
    """Run a minimal program to validate stack operations and print."""
    program = ProgramIR(
        entry=[
            Instruction(Opcode.PUSH_CONST, 1),
            Instruction(Opcode.PUSH_CONST, 2),
            Instruction(Opcode.BINARY, "+"),
            Instruction(Opcode.PRINT, 1),
            Instruction(Opcode.RETURN),
        ],
        functions={},
    )

    output = NativeVM().run(program)

    assert output == "3\n"


def test_vm_skips_runtime_type_resolution_without_operator_overloads(monkeypatch):
    """Keep ordinary binary operations on the native VM's fast path."""
    program = ProgramIR(
        entry=[
            Instruction(Opcode.PUSH_CONST, 1),
            Instruction(Opcode.PUSH_CONST, 2),
            Instruction(Opcode.BINARY, "+"),
            Instruction(Opcode.RETURN),
        ],
        functions={},
    )
    vm = NativeVM()

    def unexpected_type_lookup(_value):
        raise AssertionError("binary fast path performed a runtime type lookup")

    monkeypatch.setattr(vm, "_value_type_name", unexpected_type_lookup)

    assert vm.run(program) == ""


def test_vm_executes_function_calls_and_locals():
    """Ensure calls pass arguments and locals load correctly."""
    add_body = [
        Instruction(Opcode.LOAD, "x"),
        Instruction(Opcode.LOAD, "y"),
        Instruction(Opcode.BINARY, "+"),
        Instruction(Opcode.RETURN),
    ]
    program = ProgramIR(
        entry=[
            Instruction(Opcode.PUSH_CONST, 5),
            Instruction(Opcode.PUSH_CONST, 7),
            Instruction(Opcode.CALL, ("add", 2)),
            Instruction(Opcode.PRINT, 1),
            Instruction(Opcode.RETURN),
        ],
        functions={"add": FunctionIR(name="add", params=["x", "y"], instructions=add_body)},
    )

    output = NativeVM().run(program)

    assert output == "12\n"


def test_vm_heap_safety_checks():
    """Validate heap operations detect out-of-bounds and double free."""
    vm = NativeVM()

    ptr = vm._call("__new", [2])
    result_ok = vm._call("heap_set", [ptr, 0, 42])
    assert result_ok["e"]["code"] == 0

    result_oob = vm._call("heap_set", [ptr, 5, 99])
    assert result_oob["e"]["code"] == 1
    assert vm.error_message
    assert "out of range" in vm.error_message

    result_delete = vm._call("delete", [ptr])
    assert result_delete["e"]["code"] == 0

    result_double = vm._call("delete", [ptr])
    assert result_double["e"]["code"] == 1
    assert vm.error_message
    assert "already freed" in vm.error_message
