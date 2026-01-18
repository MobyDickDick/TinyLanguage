# Semantics suite

This document defines the initial, testable semantics suite for TinyLanguage.
The suite focuses on evaluation order and side-effect guarantees that are
important for a stricter-by-default runtime profile.

## Scope

The current suite validates the following behaviors:

1. **Left-to-right evaluation of function arguments**
   - Side effects in argument expressions must occur in the written order.
2. **Left-to-right evaluation of binary operators**
   - The left operand is evaluated before the right operand, even when the
     right operand is a nested expression.
3. **Short-circuit boolean operators**
   - `and` evaluates the right operand only when the left operand is truthy.
   - `or` evaluates the right operand only when the left operand is falsy.
4. **Left-to-right evaluation of array literals**
   - `new[...]` evaluates item expressions in order.

## Test suite mapping

The executable checks live in `tests/detailtests/test_semantics_suite.py` and
cover the suite points above:

- `test_semantics_eval_order_for_call_args`
- `test_semantics_eval_order_for_binops`
- `test_semantics_short_circuit_and_or`
- `test_semantics_eval_order_for_array_literals`

When expanding the semantics suite, add new rules here and a corresponding
pytest coverage entry in the same test module.
