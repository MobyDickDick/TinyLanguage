import textwrap

import pytest

from native_ir import FunctionIR, Instruction, Opcode, ProgramIR
from native_vm import NativeVM
from tiny_errors import SourcePos, SourceSpan
from tiny_language import NativeCodeGenerator, _parse_and_lint, run_with_native_backend


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


def test_native_code_generator_reports_not_implemented_for_try_catch():
    source = textwrap.dedent(
        """
        try {
            print("boom");
        } catch err {
            print(err);
        }
        """
    ).strip()

    with pytest.raises(NotImplementedError) as excinfo:
        run_with_native_backend(source)

    message = str(excinfo.value)
    assert "native codegen does not yet support TryCatch" in message
    assert "line 1" in message
    assert "try {" in message


def test_native_code_generator_reports_not_implemented_for_destructuring():
    source = textwrap.dedent(
        """
        { a, b } = new[1, 2];
        print(a, b);
        """
    ).strip()

    with pytest.raises(NotImplementedError) as excinfo:
        run_with_native_backend(source)

    message = str(excinfo.value)
    assert "native codegen does not yet support DestructAssign" in message
    assert "line 1" in message
    assert "{ a, b } = new[1, 2];" in message


def test_native_code_generator_reports_not_implemented_for_type_definitions():
    source = textwrap.dedent(
        """
        type Person { name: string; }
        print(1);
        """
    ).strip()

    stmts = _parse_and_lint(source)

    with pytest.raises(NotImplementedError) as excinfo:
        NativeCodeGenerator(allow_match=False, source=source).compile_program(stmts)

    message = str(excinfo.value)
    assert "native codegen does not yet support type definitions" in message
    assert "line 1" in message
    assert "type Person { name: string; }" in message


def test_native_code_generator_reports_not_implemented_for_match():
    source = textwrap.dedent(
        """
        def out = match foo {
            case _: 1;
        };
        print(out);
        """
    ).strip()

    stmts = _parse_and_lint(source)

    with pytest.raises(NotImplementedError) as excinfo:
        NativeCodeGenerator(allow_match=False, source=source).compile_program(stmts)

    message = str(excinfo.value)
    assert "native codegen does not yet support match expressions" in message
    assert "line 1" in message
    assert "match foo" in message


def test_native_code_generator_reports_not_implemented_for_heap_allocations():
    source = textwrap.dedent(
        """
        def items = new[1, 2];
        print(items);
        """
    ).strip()

    stmts = _parse_and_lint(source)

    with pytest.raises(NotImplementedError) as excinfo:
        NativeCodeGenerator(allow_heap=False, allow_match=True, source=source).compile_program(stmts)

    message = str(excinfo.value)
    assert "native codegen does not yet support heap allocations" in message
    assert "line 1" in message
    assert "def items = new[1, 2];" in message


def test_native_code_generator_reports_not_implemented_for_variant_constructors():
    source = textwrap.dedent(
        """
        def circle = Circle { radius: 2 };
        print(circle);
        """
    ).strip()

    stmts = _parse_and_lint(source)

    with pytest.raises(NotImplementedError) as excinfo:
        NativeCodeGenerator(allow_match=False, source=source).compile_program(stmts)

    message = str(excinfo.value)
    assert "native codegen does not yet support variant constructors" in message
    assert "line 1" in message
    assert "def circle = Circle { radius: 2 };" in message


def test_native_code_generator_reports_not_implemented_for_flush_arguments():
    source = "flush(1);"

    with pytest.raises(Exception) as excinfo:
        run_with_native_backend(source)

    message = str(excinfo.value)
    assert "expected SYM )" in message
    assert "line 1" in message
    assert "flush(1);" in message


def test_native_code_generator_reports_missing_type_info_for_positional_match_patterns():
    source = textwrap.dedent(
        """
        def result = match shape {
            case Circle(r) => r;
        };
        print(result);
        """
    ).strip()

    stmts = _parse_and_lint(source)

    with pytest.raises(NotImplementedError) as excinfo:
        NativeCodeGenerator(allow_match=True, source=source).compile_program(stmts)

    message = str(excinfo.value)
    assert "native codegen requires type information for positional pattern Circle" in message
    assert "line 2" in message
    assert "case Circle(r) => r;" in message


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


def test_native_vm_reports_unknown_opcode_inside_function():
    source = textwrap.dedent(
        """
        def boom() { print(1); }
        boom();
        """
    ).strip()
    program = ProgramIR(
        entry=[
            Instruction(
                Opcode.CALL,
                ("boom", 0),
                span=SourceSpan(SourcePos(2, 1), SourcePos(2, 6)),
            )
        ],
        functions={
            "boom": FunctionIR(
                name="boom",
                params=[],
                instructions=[
                    Instruction(
                        op="UNKNOWN_OP",
                        span=SourceSpan(SourcePos(1, 1), SourcePos(1, 4)),
                    )
                ],
            )
        },
    )
    vm = NativeVM(source=source)

    with pytest.raises(RuntimeError) as excinfo:
        vm.run(program)

    message = str(excinfo.value)
    assert "unknown opcode UNKNOWN_OP" in message
    assert "line 1" in message
    assert "def boom() { print(1); }" in message


def test_native_vm_reports_unknown_opcode_without_source_context():
    program = ProgramIR(
        entry=[Instruction(op="UNKNOWN_OP")],
        functions={},
    )
    vm = NativeVM(source=None)

    with pytest.raises(RuntimeError) as excinfo:
        vm.run(program)

    message = str(excinfo.value)
    assert "unknown opcode UNKNOWN_OP" in message
    assert "Supported opcodes" in message
    assert "line" not in message
    assert "col" not in message


def test_native_vm_error_lists_all_supported_opcodes():
    program = ProgramIR(
        entry=[Instruction(op="UNKNOWN_OP")],
        functions={},
    )
    vm = NativeVM(source=None)

    with pytest.raises(RuntimeError) as excinfo:
        vm.run(program)

    message = str(excinfo.value)
    supported_marker = "Supported opcodes: "
    assert supported_marker in message
    supported_text = message.split(supported_marker, 1)[1].rstrip(".")
    supported_list = [entry.strip() for entry in supported_text.split(",")]
    assert supported_list == [op.value for op in Opcode]
