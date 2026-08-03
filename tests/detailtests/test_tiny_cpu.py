import pytest

from tiny_cpu_assembler import AssemblyError, assemble, disassemble
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
