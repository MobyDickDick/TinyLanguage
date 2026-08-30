import pytest

from tiny_cpu_assembler import AssemblyError, assemble, disassemble
from tiny_cpu_cli import main
from tiny_cpu_vm import ErrorFlag, TinyCPU


def run(source: str, **kwargs) -> TinyCPU:
    cpu = TinyCPU(**kwargs)
    cpu.run(assemble(source))
    return cpu


def test_aliases_labels_arithmetic_and_io():
    cpu = run(
        """
        result := 100
        AGAIN := JUMP_ADDRESS
        LDC(7)
        STA(result)
        LOAD_CONST(5)
        ADD_ADDRESS(result)
        MUL_CONST(3)
        STORE_ADDRESS(result)
        PRINT_ADDRESS(result)
        HALT()
        """
    )
    assert cpu.output_values == [36]
    assert cpu.memory[100].value == 36
    assert cpu.memory[100].valid
    assert not cpu.error


def test_address_register_and_offset_modes():
    cpu = run(
        """
        LOAD_ADDRESS_REGISTER_CONST(20)
        LOAD_CONST(4)
        STORE_ADDRESS_REGISTER_PLUS_OFFSET(2)
        LOAD_CONST(3)
        ADD_ADDRESS_REGISTER_PLUS_OFFSET(2)
        HALT()
        """
    )
    assert (cpu.accumulator.value, cpu.accumulator.valid) == (7, True)


@pytest.mark.parametrize(
    ("operation", "addressing_mode", "setup", "expected"),
    [
        ("ADD", "CONST(7)", "", 27),
        ("ADD", "ADDRESS(31)", "LOAD_CONST(7)\nSTORE_ADDRESS(31)", 27),
        (
            "ADD",
            "ADDRESS_REGISTER()",
            "LOAD_ADDRESS_REGISTER_CONST(31)\nLOAD_CONST(7)\n"
            "STORE_ADDRESS_REGISTER()",
            27,
        ),
        (
            "ADD",
            "ADDRESS_REGISTER_PLUS_OFFSET(3)",
            "LOAD_ADDRESS_REGISTER_CONST(28)\nLOAD_CONST(7)\n"
            "STORE_ADDRESS_REGISTER_PLUS_OFFSET(3)",
            27,
        ),
        ("SUB", "CONST(7)", "", 13),
        ("SUB", "ADDRESS(31)", "LOAD_CONST(7)\nSTORE_ADDRESS(31)", 13),
        (
            "SUB",
            "ADDRESS_REGISTER()",
            "LOAD_ADDRESS_REGISTER_CONST(31)\nLOAD_CONST(7)\n"
            "STORE_ADDRESS_REGISTER()",
            13,
        ),
        (
            "SUB",
            "ADDRESS_REGISTER_PLUS_OFFSET(3)",
            "LOAD_ADDRESS_REGISTER_CONST(28)\nLOAD_CONST(7)\n"
            "STORE_ADDRESS_REGISTER_PLUS_OFFSET(3)",
            13,
        ),
    ],
)
def test_add_and_sub_use_accumulator_and_selected_operand(
    operation, addressing_mode, setup, expected
):
    """Lock down the software oracle before repairing the Logisim data paths."""

    cpu = run(f"{setup}\nLOAD_CONST(20)\n{operation}_{addressing_mode}\nHALT()")

    assert (cpu.accumulator.value, cpu.accumulator.valid) == (expected, True)
    assert not cpu.error


def test_overflow_invalidates_and_propagates_to_memory():
    cpu = run(
        """
        LOAD_CONST(32767)
        ADD_CONST(1)
        ADD_CONST(5)
        STORE_ADDRESS(10)
        HALT()
        """
    )
    assert (cpu.accumulator.value, cpu.accumulator.valid) == (0, False)
    assert (cpu.memory[10].value, cpu.memory[10].valid) == (0, False)
    assert cpu.errors == {ErrorFlag.OVERFLOW, ErrorFlag.INVALID_OPERAND}


def test_clear_error_does_not_revalidate_accumulator():
    cpu = run(
        """
        LOAD_CONST(1)
        DIV_CONST(0)
        CLEAR_ERROR()
        ADD_CONST(1)
        HALT()
        """
    )
    assert not cpu.accumulator.valid
    assert cpu.errors == {ErrorFlag.INVALID_OPERAND}


def test_error_handler_can_recover_with_a_new_valid_value():
    cpu = run(
        """
        LOAD_CONST(1)
        DIV_CONST(0)
        JUMP_ERROR(recover)
        HALT()
        recover: CLEAR_ERROR()
        LOAD_CONST(42)
        PRINT()
        HALT()
        """
    )
    assert cpu.output_values == [42]
    assert not cpu.error
    assert not cpu.halted_with_error


def test_assembler_rejects_missing_and_spurious_operands():
    with pytest.raises(AssemblyError, match="requires an operand"):
        assemble("ADD_ADDRESS()")
    with pytest.raises(AssemblyError, match="takes no operand"):
        assemble("HALT(1)")


def test_disassembly_round_trip():
    program = assemble("LOAD_CONST(2)\nADD_CONST(3)\nHALT()")
    assert assemble(disassemble(program)).instructions == program.instructions


@pytest.mark.parametrize(
    ("data_bits", "largest", "smallest"),
    [(8, 127, -128), (16, 32767, -32768), (32, 2147483647, -2147483648)],
)
def test_data_width_defines_arithmetic_range(data_bits, largest, smallest):
    cpu = run(
        f"LOAD_CONST({largest})\nADD_CONST(1)\nHALT()",
        data_bits=data_bits,
    )
    assert cpu.errors == {ErrorFlag.OVERFLOW}

    cpu = run(f"LOAD_CONST({smallest})\nHALT()", data_bits=data_bits)
    assert (cpu.accumulator.value, cpu.accumulator.valid) == (smallest, True)


@pytest.mark.parametrize(
    ("dividend", "divisor", "expected"),
    [
        (2**100 + 1, 3, (2**100 + 1) // 3),
        (-(2**100 + 1), 3, -((2**100 + 1) // 3)),
        (2**100 + 1, -3, -((2**100 + 1) // 3)),
    ],
)
def test_division_is_exact_for_wide_values_and_truncates_toward_zero(
    dividend, divisor, expected
):
    cpu = run(
        f"LOAD_CONST({dividend})\nDIV_CONST({divisor})\nHALT()",
        data_bits=128,
    )

    assert (cpu.accumulator.value, cpu.accumulator.valid) == (expected, True)
    assert not cpu.error


def test_address_width_is_independent_of_data_width():
    cpu = run(
        """
        LOAD_ADDRESS_REGISTER_CONST(200)
        LOAD_CONST(7)
        STORE_ADDRESS_REGISTER()
        PRINT_ADDRESS(200)
        HALT()
        """,
        data_bits=8,
        address_bits=8,
        memory_size=256,
    )
    assert cpu.output_values == [7]
    assert not cpu.error


def test_address_width_limits_memory_and_effective_addresses():
    with pytest.raises(ValueError, match="exceeds 4-bit address space"):
        TinyCPU(data_bits=32, address_bits=4, memory_size=17)

    cpu = run(
        """
        LOAD_ADDRESS_REGISTER_CONST(15)
        LOAD_CONST(1)
        STORE_ADDRESS_REGISTER_PLUS_OFFSET(1)
        HALT()
        """,
        data_bits=32,
        address_bits=4,
        memory_size=16,
    )
    assert ErrorFlag.INVALID_ADDRESS in cpu.errors


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"data_bits": 1}, "data_bits"), ({"address_bits": 0}, "address_bits")],
)
def test_bus_widths_have_explicit_minima(kwargs, message):
    with pytest.raises(ValueError, match=message):
        TinyCPU(**kwargs)


def test_cli_runs_with_custom_bus_widths(tmp_path, capsys):
    source = tmp_path / "wide_address.tcpu"
    source.write_text(
        "LOAD_CONST(7)\nSTORE_ADDRESS(300)\nPRINT_ADDRESS(300)\nHALT()\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--data-bits",
            "8",
            "--address-bits",
            "9",
            "--memory-size",
            "512",
            str(source),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == "7\n"


def test_cli_rejects_memory_larger_than_address_space(tmp_path, capsys):
    source = tmp_path / "halt.tcpu"
    source.write_text("HALT()\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        main(["--address-bits", "4", "--memory-size", "17", str(source)])

    assert "memory_size 17 exceeds 4-bit address space" in capsys.readouterr().err
