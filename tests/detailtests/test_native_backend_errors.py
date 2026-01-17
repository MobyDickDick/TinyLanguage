import textwrap

import pytest

from native_ir import Instruction, ProgramIR
from native_vm import NativeVM
from tiny_errors import SourcePos, SourceSpan
from tiny_language import run_with_native_backend


def test_native_code_generator_reports_not_implemented_with_location():
    source = textwrap.dedent(
        """
        def x = { a: 1 };
        print(x);
        """
    ).strip()

    with pytest.raises(NotImplementedError) as excinfo:
        run_with_native_backend(source)

    message = str(excinfo.value)
    assert "native codegen does not yet support expression ObjLit" in message
    assert "line 1" in message
    assert "def x = { a: 1 };" in message


def test_native_vm_reports_unknown_opcode_with_context():
    source = "print(1);"
    program = ProgramIR(
        entry=[
            Instruction(
                op="UNKNOWN_OP",
                span=SourceSpan(SourcePos(1, 1), SourcePos(1, 1)),
            )
        ],
        functions={},
    )
    vm = NativeVM(source=source)

    with pytest.raises(RuntimeError) as excinfo:
        vm.run(program)

    message = str(excinfo.value)
    assert "unknown opcode UNKNOWN_OP" in message
    assert "Supported opcodes" in message
    assert "line 1, col 1" in message
    assert "print(1);" in message
