# Native IR (stack-based)

This quick reference describes the internal bytecode format of the native backend. It is intentionally small so codegen and the VM stay closely aligned and tests can easily assert emitted instructions.

## Opcode overview

| Opcode | Operands | Description |
| --- | --- | --- |
| `PUSH_CONST` | Value | Push a constant onto the stack. |
| `LOAD` | Name | Load a local or global variable. |
| `STORE` | Name | Store the stack top into a variable. |
| `BINARY` | Operator (`+`, `-`, `*`, `/`, `%`, `^`, comparison operators, `&&`, `\|\|`) | Pop two values, apply the operator, and push the result. |
| `PRINT` | Count | Take the given number of stack values, format them, and print with a newline. |
| `JUMP` | Target index | Unconditional jump within the current frame. |
| `JUMP_IF_FALSE` | Target index | Conditional jump when the stack top is falsy. |
| `CALL` | `(function name, arg count)` | Collect arguments from the stack and call a function. |
| `POP` | – | Discard the top stack entry (e.g., for bare calls). |
| `RETURN` | – | End the function; optionally return the top stack value. |

## Container structures

`src/native_ir.py` collects the related data classes:

- `Instruction`: Single opcode/operand pair.
- `FunctionIR`: Bytecode and parameter list of a function.
- `ProgramIR`: Entry block and function table for the program.

The helper `format_program(program)` prints a human-friendly view of the instructions and simplifies snapshot tests.

## Beispiel

```text
entry[00]: PUSH_CONST 1
entry[01]: STORE a
entry[02]: PUSH_CONST 2
entry[03]: STORE b
entry[04]: LOAD a
entry[05]: LOAD b
entry[06]: BINARY +
entry[07]: PRINT 1
entry[08]: RETURN
function add(x, y)
  add[00]: LOAD x
  add[01]: LOAD y
  add[02]: BINARY +
  add[03]: RETURN
```

The snippet above is produced for `print(add(1, 2));` and shows the entry block plus the compiled instructions for the function `add`.
