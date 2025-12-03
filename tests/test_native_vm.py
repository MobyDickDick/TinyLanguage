from native_ir import FunctionIR, Instruction, Opcode, ProgramIR
from native_vm import NativeVM


def test_vm_runs_simple_program():
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


def test_vm_executes_function_calls_and_locals():
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
