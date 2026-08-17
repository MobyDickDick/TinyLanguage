# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

## Next documented work package (completed 2026-08-16)

- [x] **Integrate the TinyCPU OR result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Success: connect all four `OR_*` addressing modes to the extracted box and
    merge its activity-neutral result, validity, and active invalid-operand
    contribution without redrawing the maintained operation logic.
  - Result: `OrSubCircuit` is instantiated exactly once on `Operations`; the
    four controls cross the operation boundary once, while the existing shared
    accumulator, immediate, memory, and validity lanes are extended locally.
    The three maintained aggregation gates now expose their seventh input for
    OR, and no arithmetic overflow meaning was added to the bitwise operation.
  - Wiring audit: the manually revised operation boxes and their direct neutral
    behavior remain authoritative. Only the missing OR boundary, fan-out, and
    merge lanes were added, with separate top-level routes protected by the
    wired-OR and routing-conflict checks. Three documented, paired local
    tunnels cross the already occupied result, validity, and activity corridors
    on `Operations`; they avoid both hidden crossings and a broad manual redraw.
  - Follow-up: extract and integrate the `XOR_*` result-and-validity FBox under
    the same bitwise operation boundary contract.

## Next documented work package (completed 2026-08-16)

- [x] **Extract the TinyCPU OR result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Review: the latest manual redraw was compared electrically with its parent.
    Reversed wire endpoints are electrically identical, but the removed routes
    in `Operations` included driven control, result, validity, overflow, and
    invalid-operand nets; accepting that redraw would therefore change CPU
    behaviour. The maintained schematic was not rewritten to reproduce it, and
    its existing wires were left untouched.
  - Success: give all four `OR_*` addressing modes the established explicit
    accumulator/immediate-or-memory operand and validity boundary without
    arithmetic overflow semantics.
  - Result: the tunnel-free `OrSubCircuit` selects operand data and validity in
    parallel and delegates the neutral-gated bitwise operation to the leaf
    `OrArithmeticCircuit`; a generated leaf diagnostic and structural coverage
    freeze the contract.
  - Follow-up: integrate the OR box behind `Operations` and merge its result,
    validity, and invalid-operand activity without disturbing the manual layout.

## Next documented work package (completed 2026-08-16)

- [x] **Integrate the TinyCPU AND result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Success: place the manually redrawn AND box behind `Operations` and merge
    its result and validity into the maintained result and invalid-operand
    paths without changing its bitwise operand-selection contract.
  - Result: all four `AND_*` controls cross the `Operations` boundary once.
    The AND leaf retains its correct inactive identity value of `0xffff`, while
    a boundary multiplexer converts that inactive value to zero only for the
    shared OR result tree. AND validity now participates in both result
    validity and active invalid-operand detection.
  - Wiring audit: retained the manually redrawn `AndArithmeticCircuit` and
    `AndSubCircuit` layout and added only the integration lanes and explicit
    default label required by the contract.
  - Follow-up: extract and integrate the `OR_*` result-and-validity FBox under
    the same operation boundary contract.

## Next documented work package (completed 2026-08-16)

- [x] **Extract the TinyCPU AND result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Success: give all four `AND_*` addressing modes the established explicit
    accumulator/immediate-or-memory operand boundary without adding arithmetic
    overflow semantics.
  - Result: the tunnel-free `AndSubCircuit` selects operand data and validity in
    parallel and delegates the active, neutral-gated bitwise operation to the
    independently inspectable `AndArithmeticCircuit`. Structural coverage
    freezes both contracts and the generated leaf diagnostic.
  - Follow-up: integrate the AND box behind `Operations` and merge its result,
    validity, and invalid-operand activity with the maintained trees.

## Next documented work package (completed 2026-08-16)

- [x] **Integrate the TinyCPU DIV result, validity, and error FBox**
  (Owner: TinyCPU/Hardware)
  - Success: place the extracted division box behind `Operations`, merge its
    activity-gated result, validity, and signed-overflow signals with the
    existing arithmetic tree, and make an active zero divisor set the sticky
    divide-by-zero error independently of the decoder placeholder.
  - Result: all four `DIV_*` controls cross the `Operations` boundary once.
    Staged, single-driver OR gates extend the maintained four-way result lanes
    without widening or crowding them, while division validity participates in
    invalid-operand detection and `DIVIDE_BY_ZERO` exclusively drives
    `ErrorFlags.SET_DIV0`.
  - Wiring audit: restored the stable effective-address selector, memory-limit,
    range-comparator, and divisor-zero-comparator labels removed by the latest
    manual redraw; all new integration routes remain orthogonal and tunnel-free.
  - Follow-up: extract the `AND_*` result-and-validity FBox under the same
    operation boundary contract.

## Next documented work package (completed 2026-08-16)

- [x] **Extract the TinyCPU DIV result, validity, and zero-error FBox**
  (Owner: TinyCPU/Hardware)
  - Success: give all four `DIV_*` addressing modes the established explicit
    accumulator/immediate-or-memory operand boundary, while keeping the
    manually widened FBoxes and their routing corridors separate.
  - Result: the tunnel-free `DivSubCircuit` selects data and validity in
    parallel. `DivArithmeticCircuit` exports the quotient, signed-overflow and
    validity contract and explicitly detects a zero selected divisor, which is
    excluded from `RESULT_VALID`.
  - Wiring audit: restored stable labels accidentally removed from the two
    effective-address multiplexers, the address-limit constant, and its
    comparator. No component was moved back into the former crowded layout.
  - Follow-up: integrate the DIV box behind `Operations`, including its
    divide-by-zero output in the sticky error path.

## Next documented work package (completed 2026-08-16)

- [x] **Integrate the TinyCPU MUL result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Success: place the extracted multiplication box behind `Operations`, merge
    its activity-gated data, validity, and signed-overflow outputs with the
    existing ADD/SUB/NOT tree, and include invalid MUL operands in `SET_INV`.
  - Result: all four `MUL_*` controls and the shared accumulator, instruction,
    memory, and validity inputs cross the `Operations` boundary once. The
    four-way result trees and three-way arithmetic status trees merge the
    multiplication contract without adding tunnels or wired-OR nets.
  - Follow-up: extract and integrate the `DIV_*` result, validity, overflow,
    divide-by-zero, and invalid-operand paths under the same contract.

## Next documented work package (completed 2026-08-16)

- [x] **Extract the TinyCPU MUL result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Success: give all four `MUL_*` addressing modes the same explicit operand,
    result, overflow, and validity boundary already used by addition and
    subtraction, without disturbing the manually redrawn integration sheet.
  - Result: the tunnel-free `MulSubCircuit` selects immediate or memory-backed
    operands and validity in parallel and delegates signed arithmetic to the
    independently inspectable `MulArithmeticCircuit`. Structural coverage
    freezes its complete input/output contract and multiplication primitive.
  - Follow-up: place the new multiplication FBox behind `Operations` and merge
    its neutral-gated result, validity, overflow, and invalid-operand activity.

## Next documented work package (completed 2026-08-15)

- [x] **Revalidate the manually extracted TinyCPU address-range FBox**
  (Owner: TinyCPU/Hardware)
  - Success: retain the redrawn `TinyCPUMain` as a hierarchy of functional
    boxes, keep address-error combinatorics on `AddressRangeFBox`, and verify
    the effective-address selectors without restoring primitive gates to the
    integration sheet.
  - Result: the structural regression now follows the FBox boundary for the
    active offset-carry and final address-error paths. Stable, non-electrical
    labels were restored to the two retained multiplexers, comparator, and
    limit constant without moving or rewiring them, and generated diagnostics
    were refreshed from the maintained project.
  - Follow-up: extend the explicit result-and-validity operation contract to
    the next arithmetic family, beginning with `MUL_*`.

## Next documented work package (completed 2026-08-15)

- [x] **Complete the central TinyCPU effective-address range check**
  (Owner: TinyCPU/Hardware)
  - Success: reject active direct, address-register, and register-plus-offset
    memory addresses above the 12-bit `0xfff` limit, and merge that condition
    with the existing active offset-carry error before `ErrorFlags.SET_ADDR`.
  - Result: `EffectiveAddress` compares the selected 16-bit address with the
    named maximum. The top level independently combines all eight direct
    memory controls with the existing register and offset modes, so inactive
    instructions cannot set the sticky flag. A final named OR gate combines
    the range and offset-carry causes while the decoder placeholder remains
    isolated.
  - Follow-up: extend the explicit result-and-validity operation contract to
    the next arithmetic family, beginning with `MUL_*`.

## Next documented work package (completed 2026-08-15)

- [x] **Revalidate the post-increment TinyCPU program-counter range check**
  (Owner: TinyCPU/Hardware)
  - Success: retain the manually redrawn `FetchDecode` layout in which the
    program-counter increment is arranged before the range-check stage; do not
    restore the former increment constant, comparator, or error-gate positions.
  - Result: the structural regression now identifies the increment and range
    stages by their relative topology rather than obsolete absolute coordinates.
    The generated `FetchDecode` diagnostic matches the maintained circuit. The
    unrelated effective-address selector names and counter-clockwise error-gate
    terminal stubs were also preserved while refreshing all diagnostics.
  - Follow-up: complete the central address-range check for direct, register,
    and register-plus-offset results.

## Next documented work package (completed 2026-08-15)

- [x] **Revalidate the counter-clockwise TinyCPU address-error routing**
  (Owner: TinyCPU/Hardware)
  - Success: retain the manually moved, east-facing offset-error gate and its
    upward counter-clockwise input routes while ensuring that both routes end
    on actual gate terminals. Preserve stable names on the two effective-
    address multiplexers and keep generated diagnostics reproducible.
  - Result: two short vertical terminal stubs now complete the retained routes
    without moving the gate or restoring the former west-facing layout. The
    structural check resolves terminals from the gate's declared orientation,
    and both selector labels are restored at their existing positions.
  - Follow-up: complete the central address-range check for direct, register,
    and register-plus-offset results before marking the broader effective-
    address audit complete.

## Next documented work package (completed 2026-08-15)

- [x] **Integrate TinyCPU offset-carry address errors**
  (Owner: TinyCPU/Hardware)
  - Success: assert `ErrorFlags.SET_ADDR` when a register-plus-offset addressing
    mode is active and `AddressPath.OFFSET_CARRY` reports an overflow, without
    retaining the decoder's placeholder `SET_ADDR` route or flagging an
    inactive offset adder.
  - Result: the labelled `ACTIVE_OFFSET_ADDRESS_ERROR` gate combines the
    central effective-address mode with the offset carry and is the sole
    integrated source of `ErrorFlags.SET_ADDR`. Structural coverage resolves
    both inputs and the destination electrically and confirms that the decoded
    placeholder remains isolated.
  - Follow-up: complete the central address-range check for direct, register,
    and register-plus-offset results before marking the broader effective-
    address audit complete.

## Next documented work package (completed 2026-08-15)

- [x] **Revalidate the manually compacted TinyCPU integration layout**
  (Owner: TinyCPU/Hardware)
  - Success: retain the hand-adjusted `AddressPath`, `EffectiveAddress`, and
    decoder layout while reconnecting every error control by its named pin and
    keeping the effective-address selectors structurally identifiable.
  - Result: the compact `AddressPath` placement and shortened top-level routes
    remain unchanged. The reordered `FetchDecodeControls` outputs now reach
    only their matching `ErrorFlags` inputs, and the two existing address
    multiplexers again have stable labels without changing their positions or
    electrical connections. The regenerated decoder diagnostic captures the
    maintained pin order.
  - Follow-up: extend the explicit result-and-validity operation contract to
    the next arithmetic family, beginning with `MUL_*`.

## Next documented work package (completed 2026-08-15)

- [x] **Set TinyCPU `SET_INV` for active arithmetic with invalid operands**
  (Owner: TinyCPU/Hardware)
  - Success: detect an active `ADD_*` or `SUB_*` operation whose selected
    operand path is invalid, and route that condition to `ErrorFlags.SET_INV`
    without asserting the flag while arithmetic is inactive.
  - Result: `Operations` now combines the eight ADD/SUB activity controls,
    negates the combined arithmetic-valid result, and gates both conditions as
    `ACTIVE_INVALID_ARITHMETIC`. Its `INVALID_OPERAND` output is the sole
    integrated source for `ErrorFlags.SET_INV`; the decoder's placeholder
    `SET_INV` output remains isolated.
  - Follow-up: extend the same explicit result-and-validity contract to the
    next arithmetic family, beginning with `MUL_*`.

## Next documented work package (completed 2026-08-14)

- [x] **Correct the TinyCPU ADD/SUB operand and validity sources**
  (Owner: TinyCPU/Hardware)
  - Success: use the accumulator as the left operand, select the instruction's
    immediate value only for `*_CONST`, and use memory data for every direct or
    address-register-backed form. Apply the same selection to operand validity.
  - Result: `AddSubCircuit` and `SubSubCircuit` now contain parallel, labelled
    right-operand and right-valid selectors. A constant operation selects the
    16-bit instruction operand and a valid constant; all three memory forms
    select `Memory.MEMORY_DATA` and `Memory.MEMORY_VALID`. Both paths require
    `Datapath.ACC_VALID_OUT`, and subtraction remains `ACC_OUT - selected right`.
  - Integration: the manually simplified `Operations` sheet is retained. Shared
    instruction, memory, accumulator, and validity values cross its boundary
    once, while result, validity, and overflow are combined locally and leave
    the sheet through one output each.
  - Follow-up: validate and integrate `SET_INV` for an active arithmetic result
    with invalid operands, then audit the common effective-address selection.

## Next documented work package (completed 2026-08-14)

- [x] **Move the TinyCPU operation boxes to an `Operations` sheet**
  (Owner: TinyCPU/Hardware)
  - Scope: move only the three `AddSubCircuit`, `SubSubCircuit`, and
    `NotCircuit` instances (the `ADD_SUB`, `SUB_SUB`, and `NOT` functional
    boxes) from `TinyCPUMain` to a new `Operations` schematic sheet.
  - Integration: instantiate `Operations` exactly once in `TinyCPUMain` and
    expose explicit inputs and outputs for all signals currently connected to
    those three boxes. Keep the result and result-valid aggregation on
    `TinyCPUMain`; no other functional box moves as part of this package.
  - Success: the Logisim project opens with `TinyCPUMain` as its top-level
    circuit, the three operation instances occur only on `Operations`, and the
    existing ADD, SUB, and NOT signal paths and structural checks remain
    unchanged in behavior.
  - Result: `TinyCPUMain` now contains one labelled `OPERATIONS_INSTANCE` with
    explicit, typed boundary ports. The `ADD_OPERATION`, `SUB_OPERATION`, and
    `NOT_OPERATION` instances live only on the tunnel-free `Operations` sheet.
    A subsequent manual simplification moved the result, validity, and overflow
    aggregation onto that same sheet and exposes only the combined outputs.
  - Follow-up: completed by the ADD/SUB operand and validity correction above.

## Next documented work package (completed 2026-08-10)

- [x] **Integrate TinyCPU `SUB_*` accumulator results and validity**
  (Owner: TinyCPU/Hardware)
  - Success: subtract the selected immediate or memory operand from the current
    accumulator for all four `SUB_*` addressing modes and mark the result valid
    only when both inputs are valid, without changing the established load,
    `NOT`, `ADD`, or final `INPUT` priorities.
  - Result: `ACC_SUB_OPERAND_SELECT` and `ACC_SUB_VALUE` form the 16-bit
    accumulator-minus-operand result. `ACC_SUB_SELECT` applies it only for the
    four independently routed `SUB_*` controls. The parallel validity path
    selects the matching operand validity, combines it with
    `Datapath.ACC_VALID_OUT`, and inserts the result after `ADD` and before the
    final `INPUT` override.
  - Follow-up: integrate the `MUL_*` result data and validity as the next
    explicitly documented binary family.

## Next documented work package (completed 2026-08-10)

- [x] **Propagate TinyCPU `ADD_*` validity to the accumulator**
  (Owner: TinyCPU/Hardware)
  - Success: require a valid accumulator and a valid selected operand for all
    four `ADD_*` addressing modes, while preserving the established load,
    `NOT`, and final `INPUT` validity priorities.
  - Result: `ACC_ADD_OPERAND_VALID_SELECT` chooses a valid immediate or
    `Memory.MEMORY_VALID`; `ACC_ADD_VALID` combines it with
    `Datapath.ACC_VALID_OUT`. `ACC_ADD_VALID_SELECT` applies that result only
    for the four independently routed `ADD_*` controls.
  - Follow-up: integrate the `SUB_*` result data and validity as the next
    explicitly documented binary family.

## Next documented work package (completed 2026-08-10)

- [x] **Propagate TinyCPU `NOT` validity to the accumulator**
  (Owner: TinyCPU/Hardware)
  - Success: select the accumulator's current valid bit for `Datapath.VALID_IN`
    while the unary `NOT` result is selected, without changing the established
    load or `INPUT` validity priorities.
  - Result: `ACC_NOT_VALID_SELECT` sits between the memory-validity and input-
    validity stages. Its independent `NOT` control selects
    `Datapath.ACC_VALID_OUT`; otherwise it preserves the immediate-or-memory
    validity. `INPUT_VALID` remains the final override.
  - Follow-up: integrate binary accumulator-result validity, beginning with one
    explicitly documented instruction family and its operand-validity rules.

## Next documented work package (completed 2026-08-10)

- [x] **Propagate TinyCPU memory validity to the accumulator**
  (Owner: TinyCPU/Hardware)
  - Success: select `Memory.MEMORY_VALID` for `Datapath.VALID_IN` whenever the
    existing memory-backed accumulator data path is selected, while retaining
    the valid constant for immediate operands and the independent `INPUT`
    validity override.
  - Result: the labelled `ACC_MEMORY_VALID_SELECT` multiplexer mirrors
    `ACC_MEMORY_SELECT`: its default is the valid constant and its memory input
    is `Memory.MEMORY_VALID`. Its output feeds the default side of
    `ACC_INPUT_VALID_SELECT`, so `INPUT_VALID` still has final priority only for
    `INPUT`. Structural coverage protects the sources, shared selection net,
    staged destination, and isolation from `Datapath.DATA_IN`.
  - Follow-up: integrate accumulator result validity for the arithmetic and
    logic instruction families, one explicitly documented group at a time.

## Next documented work package (completed 2026-08-10)

- [x] **Propagate TinyCPU `INPUT` validity to the accumulator**
  (Owner: TinyCPU/Hardware)
  - Success: expose an independent one-bit `INPUT_VALID` top-level pin and
    select it for `Datapath.VALID_IN` only while the `INPUT` decoder output is
    active, without coupling the validity and 16-bit data nets.
  - Result: the labelled `ACC_INPUT_VALID_SELECT` multiplexer normally supplies
    the valid constant used by the currently integrated operand path and
    selects `INPUT_VALID` for `INPUT`. Structural coverage protects both
    sources, the shared `INPUT` selection control, the datapath destination,
    and isolation from `Datapath.DATA_IN`.
  - Follow-up: integrate `Memory.MEMORY_VALID` for memory-backed accumulator loads
    through an explicit validity-selection stage.

## Next documented work package (completed 2026-08-10)

- [x] **Rebaseline TinyCPU integration checks after the corrected redraw**
  (Owner: TinyCPU/Hardware)
  - Success: treat the manually corrected component positions and direct routes
    in `TinyCPU.circ` as authoritative instead of restoring coordinates and
    tunnels from the superseded drawing.
  - Result: structural tests now resolve the corrected automatic-symbol input
    edge, follow the relocated decode and error-control endpoints, and protect
    the direct accumulator data routes. Cosmetic labels identify the three
    accumulator selectors. The checks also exposed and corrected the two
    crossed selector controls from the redraw: `NOT` now selects the inverted
    accumulator stage, while `INPUT` selects only the external-value stage.
  - Follow-up: connect the accumulator-validity control required by `INPUT`.

## Next documented work package (completed 2026-08-10)

- [x] **Select the external accumulator value for TinyCPU `INPUT`**
  (Owner: TinyCPU/Hardware)
  - Success: expose a 16-bit `INPUT_VALUE` top-level pin and select it through
    an explicitly labelled final multiplexer only while the independent
    `INPUT` decoder output is active.
  - Result: `ACC_INPUT_SELECT` passes the existing operand, memory, or inverted
    accumulator result by default and selects `INPUT_VALUE` for `INPUT`. The
    checked-in route preserves separate 16-bit data and one-bit selection nets.
    Under the current design rule, its remaining long-distance tunnels are
    transitional exceptions and must be replaced by visible wiring whenever a
    collision-free redraw makes that possible.
  - Follow-up: connect the accumulator-validity control required by `INPUT`.

## Next documented work package (completed 2026-08-09)

- [x] **Select the inverted accumulator for TinyCPU `NOT`**
  (Owner: TinyCPU/Hardware)
  - Success: derive a 16-bit inverted value from `Datapath.ACC_OUT` and select
    it through an explicitly labelled second-stage multiplexer only when the
    independent `NOT` decoder output is active.
  - Result: `ACC_NOT_VALUE` and `ACC_NOT_SELECT` add the first computed
    accumulator source without changing the existing operand-versus-memory
    selection. Structural coverage verifies component widths, the staged data
    path, the `NOT` select path, and isolation from the `INPUT` control. The
    package also restores the clock, reset, and labelled data-selection routes
    lost in the preceding manual redraw.
  - Follow-up: integrate the external value used by `INPUT` as the next
    explicitly documented accumulator source.

## Next documented work package (completed 2026-08-09)

- [x] **Select memory data for TinyCPU `LOAD_ADDRESS_REGISTER_PLUS_OFFSET`**
  (Owner: TinyCPU/Hardware)
  - Success: add `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` to the explicitly labelled
    gate before `ACC_DATA_SELECT`, keeping all three decoder outputs independent
    and all 16-bit data paths unchanged.
  - Result: `ACC_MEMORY_SELECT` now selects memory data for every memory-backed
    load addressing mode. The structural regression verifies all three causes,
    their electrical isolation, the gate-to-selector path, and continued
    separation from every data-bus endpoint.
  - Follow-up: integrate the next accumulator data source required by `NOT` or
    `INPUT`, one explicitly documented source at a time.

## Next documented work package (completed 2026-08-09)

- [x] **Select memory data for TinyCPU `LOAD_ADDRESS_REGISTER`**
  (Owner: TinyCPU/Hardware)
  - Success: combine `LOAD_ADDRESS` and `LOAD_ADDRESS_REGISTER` through an
    explicit labelled gate before `ACC_DATA_SELECT`, keeping both decoder
    outputs independent and all 16-bit data paths unchanged.
  - Result: `ACC_MEMORY_SELECT` gives each addressing mode its own input and
    drives the accumulator-data multiplexer select line alone. The structural
    regression verifies both causes, their electrical isolation, the gate-to-
    selector path, and continued separation from all data-bus endpoints.
  - Follow-up: add `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` as the next explicitly
    documented memory-data selection cause.

## Next documented work package (completed 2026-08-09)

- [x] **Select memory data for TinyCPU `LOAD_ADDRESS`**
  (Owner: TinyCPU/Hardware)
  - Success: replace the direct operand connection with a labelled 16-bit
    multiplexer that keeps the instruction operand and `Memory.MEMORY_DATA` on
    independent inputs, selects memory only for `LOAD_ADDRESS`, and remains
    isolated from opcode, write-control, and validity nets.
  - Result: `ACC_DATA_SELECT` now makes the instruction operand the default
    accumulator input and routes memory data for the first memory-backed load.
    A structural regression resolves both sources and the select control by
    signal name and verifies source, control, and output isolation.
  - Follow-up: extend memory-data selection to the address-register addressing
    modes one explicitly documented mode at a time.

## Next documented work package (completed 2026-08-09)

- [x] **Connect the TinyCPU instruction operand to the accumulator data input**
  (Owner: TinyCPU/Hardware)
  - Success: route the splitter's 16-bit operand output to
    `Datapath.DATA_IN` on a dedicated net, without coupling it to the 6-bit
    opcode output or the adjacent one-bit accumulator controls.
  - Result: the first accumulator data source now reaches the datapath through
    a free corridor around the maintained top-level symbols. A structural
    regression checks the intended endpoints and bus isolation.
  - Follow-up: integrate the next accumulator data source through explicit
    selection logic before connecting memory-backed write operations.

## Next documented work package (completed 2026-08-09)

- [x] **Integrate the TinyCPU `INPUT` accumulator-write control**
  (Owner: TinyCPU/Hardware)
  - Success: add `INPUT` to the second-stage `ACC_WRITE_REQUEST` gate on an
    independent net while retaining the 32-family aggregator and unary `NOT`
    causes and preserving isolation from `Datapath.DATA_IN`.
  - Result: the explicitly three-input second-stage gate now combines the
    family request, `INPUT`, and `NOT` without coupling decoder outputs. The
    structural regression resolves controls and gates by their labels and checks
    electrical reachability, so moving the hand-maintained drawing does not
    invalidate the test.
  - Follow-up: integrate the accumulator data-source selection required by
    these write-enable controls, one explicitly documented source at a time.


## Next documented work package (completed 2026-08-09)

- [x] **Add the TinyCPU XOR-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add all four `XOR_*` decoder outputs to `ACC_LOAD_REQUEST` on
    independent nets while retaining the twenty-eight existing `LOAD_*`,
    `ADD_*`, `SUB_*`, `MUL_*`, `DIV_*`, `AND_*`, and `OR_*` causes and
    isolation from `Datapath.DATA_IN`.
  - Result: the explicitly thirty-two-input accumulator-write gate covers all
    eight complete four-mode instruction families. Structural coverage models
    Logisim endpoint-on-wire junctions, preventing accidental wired-ORs while
    checking every source, gate input, destination, and sibling-net isolation.
  - Follow-up: add the unary `NOT` accumulator-write control as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Add the TinyCPU OR-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add all four `OR_*` decoder outputs to `ACC_LOAD_REQUEST` on
    independent nets while retaining the twenty-four existing `LOAD_*`,
    `ADD_*`, `SUB_*`, `MUL_*`, `DIV_*`, and `AND_*` causes and isolation from
    `Datapath.DATA_IN`.
  - Result: the explicitly twenty-eight-input accumulator-write gate covers
    all seven complete instruction families; parameterized structural coverage
    locks every source, gate input, destination, and sibling-net isolation.
  - Follow-up: add the four `XOR_*` accumulator-writing controls as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Add the TinyCPU AND-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add all four `AND_*` decoder outputs to `ACC_LOAD_REQUEST` on
    independent nets while retaining the twenty existing `LOAD_*`, `ADD_*`,
    `SUB_*`, `MUL_*`, and `DIV_*` causes and isolation from
    `Datapath.DATA_IN`.
  - Result: the explicitly twenty-four-input accumulator-write gate covers all
    six complete instruction families; parameterized structural coverage locks
    every source, gate input, destination, and sibling-net isolation.
  - Follow-up: add the four `OR_*` accumulator-writing controls as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Add the TinyCPU divide-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add all four `DIV_*` decoder outputs to `ACC_LOAD_REQUEST` on
    independent nets while retaining the sixteen existing `LOAD_*`, `ADD_*`,
    `SUB_*`, and `MUL_*` causes and isolation from `Datapath.DATA_IN`.
  - Result: the explicitly twenty-input accumulator-write gate covers all
    five complete instruction families; parameterized structural coverage
    locks every source, gate input, destination, and sibling-net isolation.
  - Follow-up: add the four `AND_*` accumulator-writing controls as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Add the TinyCPU multiply-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add all four `MUL_*` decoder outputs to `ACC_LOAD_REQUEST` on
    independent nets while retaining the twelve existing `LOAD_*`, `ADD_*`,
    and `SUB_*` causes and isolation from `Datapath.DATA_IN`.
  - Result: the explicitly sixteen-input accumulator-write gate covers all
    four complete instruction families; parameterized structural coverage
    locks every source, gate input, destination, and sibling-net isolation.
  - Follow-up: add the four `DIV_*` accumulator-writing controls as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Add the TinyCPU subtract-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add all four `SUB_*` decoder outputs to `ACC_LOAD_REQUEST` on
    independent nets while retaining the eight existing `LOAD_*` and `ADD_*`
    causes and isolation from `Datapath.DATA_IN`.
  - Result: the explicitly twelve-input accumulator-write gate covers all
    three complete instruction families; parameterized structural coverage
    locks every source, gate input, destination, and sibling-net isolation.
  - Follow-up: add the four `MUL_*` accumulator-writing controls as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Add the TinyCPU add-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add all four `ADD_*` decoder outputs to `ACC_LOAD_REQUEST` on
    independent nets while retaining the four existing `LOAD_*` causes and
    isolation from `Datapath.DATA_IN`.
  - Result: the explicitly eight-input accumulator-write gate covers both
    complete instruction families; parameterized structural coverage locks
    every source, gate input, destination, and sibling-net isolation.
  - Follow-up: add the four `SUB_*` accumulator-writing controls as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Complete the TinyCPU load-family accumulator controls**
  (Owner: TinyCPU/Hardware)
  - Success: add `LOAD_ADDRESS_REGISTER` and
    `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` to `ACC_LOAD_REQUEST` while keeping all
    four decoder outputs on independent nets and keeping the request away from
    `Datapath.DATA_IN`.
  - Result: the explicitly four-input accumulator-load gate now covers every
    `LOAD_*` addressing mode; parameterized structural coverage locks each
    input, the `ACC_LOAD` destination, and isolation from the data input.
  - Follow-up: add the four `ADD_*` accumulator-writing controls as the next
    explicitly documented instruction group.

## Next documented work package (completed 2026-08-09)

- [x] **Aggregate the first TinyCPU accumulator-load controls**
  (Owner: TinyCPU/Hardware)
  - Success: connect `LOAD_ADDRESS` to `Datapath.ACC_LOAD` together with the
    existing `LOAD_CONST` cause through explicit combinational logic, without
    wiring the two decoder outputs directly onto one driven net.
  - Result: a named `ACC_LOAD_REQUEST` OR gate combines the two independent
    causes; parameterized structural coverage proves that either cause reaches
    `ACC_LOAD` while the decoder outputs remain electrically isolated.
  - Follow-up: add the remaining accumulator-writing instruction groups to
    the aggregation logic one explicitly documented group at a time.

## Next documented work package (completed 2026-08-08)

- [x] **Connect the remaining TinyCPU top-level sticky-error controls**
  (Owner: TinyCPU/Hardware)
  - Success: connect `SET_ADDR`, `SET_INV`, `SET_ILL`, and `SET_INPUT` from
    `FetchDecodeControls` to the matching `ErrorFlags` inputs without coupling
    any of the long routes to an existing top-level net.
  - Result: every remaining signal has a dedicated outer-right lane, and a
    parameterized structural regression locks both endpoint reachability and
    isolation from clock, reset, opcode, and every sibling error-control net.
  - Follow-up: integrate the data-path control nets individually.

## Next documented work package (completed 2026-08-08)

- [x] **Connect the TinyCPU top-level divide-by-zero-error control**
  (Owner: TinyCPU/Hardware)
  - Success: connect the one-bit `FetchDecodeControls.SET_DIV0` output to the
    matching `ErrorFlags.SET_DIV0` input without moving existing components or
    coupling the control to any previously integrated top-level net.
  - Result: the second sticky-error set control uses a dedicated outer-right
    lane; a structural regression locks both endpoints and its isolation from
    clock, reset, opcode, clear-error, and overflow-error nets.
  - Follow-up: connect the remaining sticky-error set controls one at a time,
    beginning with `SET_ADDR` and its matching `ErrorFlags` input.

## Next documented work package (completed 2026-08-08)

- [x] **Connect the TinyCPU top-level overflow-error control**
  (Owner: TinyCPU/Hardware)
  - Success: connect the one-bit `FetchDecodeControls.SET_OVF` output to the
    matching `ErrorFlags.SET_OVF` input without moving existing components or
    coupling the control to clock, reset, opcode, or clear-error nets.
  - Result: the first sticky-error set control uses its own outer-right lane;
    a structural regression follows the automatic-symbol terminals and locks
    the connection and its isolation from all previously integrated nets.
  - Follow-up: connect the remaining sticky-error set controls one at a time,
    beginning with `SET_DIV0` and its matching `ErrorFlags` input.

## Next documented work package (completed 2026-08-06)

- [x] **Connect the TinyCPU top-level clear-error control**
  (Owner: TinyCPU/Hardware)
  - Success: connect the one-bit `FetchDecodeControls.CLEAR_ERROR` output to
    the matching `ErrorFlags.CLEAR_ERROR` input without moving existing
    components or coupling the control to clock, reset, or the opcode bus.
  - Result: the first decoded one-bit control uses the free outer-right
    corridor around every block; a structural regression follows the real
    automatic-symbol terminals and locks its isolation from existing nets.
  - Follow-up: connect the sticky-error set controls one at a time, beginning
    with `SET_OVF` and its matching `ErrorFlags` input.

## Next documented work package (completed 2026-08-06)

- [x] **Connect the TinyCPU top-level opcode decode net**
  (Owner: TinyCPU/Hardware)
  - Success: place the existing `FetchDecodeControls` block on the maintained
    overview and connect only the 22-bit `FetchDecode.OPCODE` output to its
    matching `FetchDecodeControls.OPCODE` input, without moving existing
    components or coupling the bus to clock or reset.
  - Result: the first decode-control net runs around the left edge of the
    overview in a free orthogonal corridor; a structural regression follows
    the actual automatic-symbol terminals and locks the isolated connection.
  - Follow-up: expose and connect one one-bit decoded control at a time,
    beginning with `CLEAR_ERROR` and its matching `ErrorFlags` input.

## Next documented work package (completed 2026-08-06)

- [x] **Connect the TinyCPU top-level reset net**
  (Owner: TinyCPU/Hardware)
  - Success: add one external `RESET` input and connect it exclusively to
    `FetchDecode.RESET`, without moving the hand-maintained overview or
    implicitly clearing the accumulator, address register, RAM, or errors.
  - Result: the one-bit reset net uses the free corridor below the overview to
    reach the Fetch/Decode reset terminal from the right; a structural
    regression follows the actual wire graph and excludes every other block.
  - Follow-up: connect the decode-control nets one at a time, starting with an
    independently named Fetch/Decode output and its matching contract input.

## Next documented work package (completed 2026-08-06)

- [x] **Complete the TinyCPU top-level clock fan-out**
  (Owner: TinyCPU/Hardware)
  - Success: connect the existing top-level clock net to `ErrorFlags.CLK`
    without moving the hand-maintained overview or crossing another symbol,
    and lock all five stateful clock terminals with a structural regression.
  - Result: a new orthogonal branch uses the free corridor above the overview;
    the focused regression follows the real generated-symbol terminals from
    the single `CLK` input to Fetch/Decode, datapath, address path, memory, and
    error flags.
  - Follow-up: install the independently specified `RESET` net as the next
    isolated top-level integration step.

## Next documented work package (completed 2026-08-04)

- [x] **Promote the TinyCPU reproducibility verifier to a dedicated CI gate**
  (Owner: TinyCPU/Hardware)
  - Success: the main CI job runs the documented fresh-checkout acceptance
    command before the general test suite, and a regression prevents the gate
    from being removed accidentally.
  - Result: CI now runs `PYTHONPATH=src python src/tiny_cpu_verify.py` as a
    named hardware reproducibility gate; focused coverage locks both the step
    name and exact acceptance command, and the hardware roadmap documents the
    post-AP-8 baseline-maintenance policy.
  - Follow-up: future circuit or machine-format work must start a newly scoped
    roadmap cycle while retaining this gate as the baseline compatibility
    check.

## Next documented work package (completed 2026-08-03)

- [x] **Complete TinyCPU AP 8 documentation and reproducibility checks**
  (Owner: TinyCPU/Hardware)
  - Success: document operation and schematic architecture and provide an
    automated acceptance command that a fresh checkout can reproduce.
  - Result: the hardware guide now defines the state-owning sheets, simulation
    boundary, acceptance workflow, and artifact recovery paths; the standalone
    verifier checks connectivity, the versioned contract, generated and
    embedded ROM artifacts, the listing, and the 17-edge VM trace.
  - Follow-up: the eight-package TinyCPU hardware baseline is complete; future
    behavior or machine-format changes require a newly scoped roadmap cycle.

## Next documented work package (completed 2026-08-03)

- [x] **Complete the TinyCPU AP 6 symbolic ISA control surface**
  (Owner: TinyCPU/Hardware)
  - Success: extend the provisional hardware decode boundary across every
    addressing mode, arithmetic and logic operation, jump, I/O instruction,
    and sticky-error path; parameterized structural checks must cover every
    instruction defined by the Python ISA.
  - Result: the six-bit provisional decoder now exposes every symbolic ISA
    control, all three branch-condition inputs, and all six error-set outputs;
    the machine-readable profile and tests derive complete coverage from
    `INSTRUCTION_SET`, while the AP 5 countdown remains frozen.
  - Follow-up: AP 7 must assign versioned opcodes and a word layout and use an
    encoder to produce the ROM image and listing.

## Next documented work package (completed 2026-08-03)

- [x] **Integrate the TinyCPU AP 5 core program**
  (Owner: TinyCPU/Hardware)
  - Success: load a reproducible counting-loop fixture and compare every
    clock-edge state, output, and halt result with the Python VM.
  - Result: the provisional ROM now contains a core-only countdown program;
    its 17-edge JSON trace freezes PC, accumulator validity, flags, watched
    memory, output, and halt state, and a reusable comparator reports divergent
    edge fields.
  - Follow-up: AP 6 can extend the remaining addressing modes, arithmetic,
    logic, jumps, and I/O while retaining the AP 5 trace as a core regression.

## Next documented work package (completed 2026-08-03)

- [x] **Implement TinyCPU AP 4 fetch and decode**
  (Owner: TinyCPU/Hardware)
  - Success: add a 12-bit PC, instruction ROM, and decode/control path for
    `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT`, and
    `HALT`; an out-of-range PC must set `ADDR` and halt with an error.
  - Result: the connected `FetchDecode` sheet exposes the six core controls,
    operand and PC state, selects sequential or conditional-jump PC updates,
    and turns the program-limit comparison into `SET_ADDR` plus `HALT_ERROR`.
    The machine-readable contract and structural regressions freeze AP 4.
  - Follow-up: AP 5 must load a reproducible counting-loop fixture and compare
    every clock-edge state, output, and halt result with the Python VM.

## Next documented work package (completed 2026-08-03)

- [x] **Implement TinyCPU AP 3 memory and error registers**
  (Owner: TinyCPU/Hardware)
  - Success: connect value and validity RAM to one address, write-enable, and
    clock interface; implement all six set-dominant sticky error flags with a
    shared `CLEAR_ERROR`; freeze both interfaces in the hardware profile and
    structural regressions.
  - Result: the Logisim `Memory` and `ErrorFlags` sheets are connected, the
    contract inspector validates their pins and logic components, and AP 3 is
    marked complete in the hardware roadmap.
  - Follow-up: AP 4 must add PC, instruction ROM, and fetch/decode control for
    the documented core instruction subset.

## Next documented work package (completed 2026-08-03)

- [x] **Reject duplicate keys in YAML block mappings**
  (Owner: Language/Stdlib)
  - Success: reject duplicate mapping keys instead of silently retaining the
    last value, and identify the duplicate's one-based source line at the root,
    in nested mappings, and in inline mapping entries inside block lists.
  - Result: the conservative YAML parser now reports duplicate keys with their
    source line, and parameterized regressions cover all three mapping shapes.
  - Follow-up: advanced YAML features such as anchors, aliases, tags, complex
    keys, and multi-document streams remain explicit non-goals.

## Next documented work package (completed 2026-08-02)

- [x] **Add line-aware diagnostics for malformed YAML block collections**
  (Owner: Language/Stdlib)
  - Success: deterministic parse failures identify the offending source line
    for inconsistent indentation, tab indentation, and mixed collection styles.
  - Result: YAML block-parser errors now include one-based input line numbers,
    with parameterized regressions covering the three malformed-input classes.
  - Follow-up: advanced YAML features such as anchors, aliases, tags, complex
    keys, and multi-document streams remain explicit non-goals.

## Next documented work package (completed 2026-08-02)

- [x] **Support inline mapping entries inside YAML block lists**
  (Owner: Language/Stdlib)
  - Success: parse sequence items whose first string-keyed mapping entry shares
    the dash line (for example, `- name: Tiny`), including continuation keys
    and recursively nested block collections.
  - Result: inline mapping items are normalized into the recursive block
    parser, and a regression locks multiple mapping items, scalar continuation
    keys, nested lists, and colon-containing scalar values to exact JSON.
  - Follow-up: advanced YAML features such as quoted keys, anchors, aliases,
    tags, and multi-document streams remain explicit non-goals.

## Next documented work package (completed 2026-07-26)

- [x] **Extend `stdlib.yaml` parsing to nested block collections**
  (Owner: Language/Stdlib)
  - Success: parse consistently indented block-style lists and string-keyed
    maps recursively while retaining JSON-compatible scalar types.
  - Result: the conservative YAML parser now recognizes nested map/list blocks,
    empty mapping values introduce child collections, and a regression locks a
    mixed map/list document to its exact JSON representation.
  - Follow-up: inline mapping entries inside block lists (for example,
    `- name: Tiny`) remain outside this small grammar and need separate scope.

## Next documented work package (completed 2026-07-26)

- [x] **Lock `stdlib.yaml` JSON-compatible scalar round-trip coverage**
  (Owner: Language/Stdlib)
  - Success: reparse deterministic YAML serialization and verify that integers,
    negative and decimal numbers, booleans, nulls, empty and Unicode strings,
    and inline lists retain their values and scalar types.
  - Result: YAML scalar parsing now delegates valid JSON scalar text to the
    runtime JSON parser, while plain YAML strings remain strings; a regression
    checks the complete reparsed structure against the typed source values.
  - Follow-up: nested block-style lists and maps remain outside the conservative
    initial YAML subset and require a separately scoped parser extension.

## Open-task audit (2026-07-22)

- [x] **Re-validate the documented backlog before opening the next cycle**
  (Owner: Project Lead)
  - Result: no unchecked checklist entries (`- [ ]`) remain in the tracked
    planning surfaces (`docs/`, `documentation_tasks.md`, and `README.md`)
    as of 2026-07-22, so there is no implementation-ready documented work
    package to execute without first adding newly scoped work.
  - Follow-up: start the next cycle by triaging fresh candidates into this
    file with owners, success criteria, and acceptance notes before future
    "next documented work package" requests are executed.


## Next documented work package (completed 2026-07-22)

- [x] **Lock `stdlib.csv` parser round-trip edge coverage**
  (Owner: Language/Stdlib)
  - Success: add a deterministic CSV round-trip regression for quoted fields,
    embedded newlines, and CRLF input normalization, as called out by the data
    interchange parser round-trip follow-up in `docs/stdlib_expansion_plan.md`.
  - Result: `tests/detailtests/test_stdlib_csv.py` now reparses serialized CSV
    output and verifies stable row counts plus field preservation for embedded
    delimiters and multiline fields.
  - Follow-up: YAML remains optional for Phase 2 and should receive equivalent
    round-trip coverage once a backend implementation is available.

## Active timebox (2026-02-15 refresh)

The following items were promoted from the roadmap into an active execution
window. They remain open until the listed success criteria are met.

- [x] **Improve source-span accuracy in parser/interpreter diagnostics**
  (Owner: Frontend)
  - Success: parser/runtime errors include stable line+column spans and at
    least one regression test locks in the emitted span for malformed input.
  - Notes: added `test_parser_error_reports_stable_multiline_span_for_malformed_input`
    in `tests/detailtests/test_spans.py` to lock parser `TinyLangError` span
    coordinates and rendered line context for malformed input.

- [x] **Strengthen heap API diagnostics and safety checks** (Owner: Runtime)
  - Success: invalid pointer, out-of-bounds access, and double-delete paths
    produce distinct user-facing messages with dedicated detail tests.
  - Notes: added `tests/detailtests/test_heap_api_diagnostics_messages.py`
    with dedicated coverage for invalid-pointer (`heap_get(0, 0)`),
    out-of-bounds (`heap_get(ptr, 5)`), and double-delete diagnostics,
    asserting each path emits the expected user-facing message pattern.

- [x] **Expand heap stress/regression coverage** (Owner: Runtime)
  - Success: add tests for nested arrays, larger `new/delete` churn, and deep
    recursion interaction with heap allocation/deallocation.
  - Notes: expanded `tests/detailtests/test_heap_api_errors.py` with dedicated
    nested-pointer, high-churn allocation/deallocation, and deep-recursion
    heap-unwind scenarios that assert leak-report stability and expected output.

- [x] **Tooling ergonomics pass for CLI + formatter/LSP workflow docs**
  (Owner: Tooling)
  - Success: `docs/cli_workflows.md` and
    `docs/language_server_workflows.md` each receive one end-to-end workflow
    update validated by the corresponding tests.
  - Notes: `docs/cli_workflows.md` now documents the typecheck-then-backend
    execution workflow and `docs/language_server_workflows.md` documents the
    project formatting/code-actions roundtrip; both flows are locked by
    `test_tiny_cli_typecheck_then_backend_run_workflow` and
    `test_cli_project_formatting_hook_matches_format_output`.


## Priority execution update (2026-05-02)

- [x] **Process highest-priority active task** (Owner: Project Lead)
  - Result: no unchecked (`- [ ]`) tasks remain in tracked planning documents
    (`docs/`, `documentation_tasks.md`) as of 2026-05-02, so execution focus
    shifts to preparing the next triage cycle and promoting new candidates into
    the upcoming active timebox.


## Next documented step (executed 2026-05-04)

- [x] **Prepare the next triage cycle candidate slate** (Owner: Project Lead)
  - Success: promote at least three clearly scoped candidates into a dated, owner-tagged shortlist so the upcoming triage meeting can convert them into an active timebox without re-discovery work.
  - Notes: consolidated a 2026-06 triage shortlist with owners, sequencing, and acceptance outcomes directly in this tracker so the next planning pass can promote items without additional discovery.

### 2026-06 triage shortlist (ready for promotion)

1. **Typecheck CI gate trial** (Owner: Language/Tooling) — completed 2026-06-06
   - Outcome target: add an opt-in CI job that runs type-check/lint mode on a curated fixture set and publishes a baseline report for false-positive review.
   - Result: added a manually dispatched `typecheck-gate-trial` CI job, a deterministic reporting tool, three manifest-backed fixtures (including an E009 positive control), and regression coverage for baseline drift and review-required findings.
2. **Native backend error-parity audit** (Owner: Runtime/Compiler) — completed 2026-06-06
   - Outcome target: run a focused interpreter vs. native error-message parity audit and capture remaining deltas as bounded follow-up issues.
   - Result: added an executable exact-message parity matrix, documented the audit method and passing scenarios, and bounded the remaining native `len` and exception-metadata deltas as `NBEP-001` and `NBEP-002`.
3. **Package manager reproducibility hardening** (Owner: Ecosystem) — completed 2026-06-11
   - Outcome target: extend lockfile reproducibility coverage with additional path edge-cases and document the deterministic rendering contract.
   - Result: lockfile rendering now lexically normalizes redundant path segments and dependency-override paths, TOML-escapes every persisted string, and is covered by repeated-write, LF-ending, quoted-path, override, and dot-segment regressions. The byte-level ordering, path, encoding, and checksum rules are documented in `docs/package_manager_plan.md`.

## Next documented work package (completed 2026-06-12)

- [x] **NBEP-001: implement native `len` built-in parity**
  (Owner: Runtime/Compiler)
  - Success: valid string, collection, and heap-pointer calls return the same
    value in the interpreter and native VM; unsized values produce the exact
    interpreter `E005` diagnostic.
  - Result: added native `len` dispatch and parity regressions for all supported
    value categories, moved the unsized-value scenario into the exact-message
    matrix, and closed `NBEP-001` in the audit document.
  - Follow-up: `NBEP-002` remains separately bounded to exception metadata and
    deliberately does not change CLI-rendered diagnostics.

- [x] **NBEP-002: inventory native exception metadata parity**
  (Owner: Runtime/Compiler)
  - Success: inventory error type, code, hint, position, and span for every
    scenario in the native error-parity audit; publish the intended Python API
    contract without changing CLI-rendered text.
  - Result: added an executable metadata matrix for all five audit scenarios and
    documented the supported distinction between structured `TinyLangError`
    failures and opaque native `RuntimeError` failures. Backend-neutral clients
    use the already parity-checked rendered diagnostic.
  - Follow-up: no bounded issues remain from the focused native error-parity
    audit; future deltas receive new issue identifiers and explicit scope.

## Next documented work package (completed 2026-06-13)

- [x] **Resolve the `stdlib.path` architecture and normalization contract**
  (Owner: Language/Stdlib)
  - Success: decide whether `stdlib.path` wraps `File` or owns a dedicated
    namespace; document the filesystem boundary and lock the decision with a
    regression covering nonexistent paths plus lexical `.`/`..` reduction.
  - Result: selected a dedicated, filesystem-independent `Path` namespace,
    documented the boundary in the expansion plan, made `Path.join` apply the
    same lexical normalization as `Path.normalize`, and added an end-to-end
    regression proving path operations do not require the target to exist.
  - Follow-up: the next unresolved Phase 1 decision is the cross-platform
    guarantee for `stdlib.os` separators, case sensitivity, and environment
    variable handling.

## Next documented work package (completed 2026-06-20)

- [x] **Close stale conformance-strategy follow-ups**
  (Owner: Tooling/QA)
  - Success: resolve the remaining open follow-up bullets in
    `docs/conformance_compatibility_test_strategy.md` by tying stdlib ownership
    to the suite-boundary matrix and revalidating the local smoke command
    against the 60-second feedback budget.
  - Result: the stdlib ownership follow-up now points to explicit spec/parity/
    compatibility responsibilities, and the smoke-subset follow-up records the
    `python src/run_all.py --smoke` validation performed on 2026-06-20.
  - Follow-up: future smoke-tier expansions should keep the same command under
    60 seconds or move slower checks into nightly/full CI lanes.

## Next documented work package (completed 2026-06-20)

- [x] **Define the `stdlib.os` cross-platform contract**
  (Owner: Language/Stdlib)
  - Success: document separator, case-sensitivity, and environment-variable
    behavior, and lock the contract with regression coverage.
  - Result: `docs/stdlib_expansion_plan.md` now documents the Phase 1
    `stdlib.os` portability boundary; `os.env_case_sensitive()` exposes host
    environment key semantics; and `tests/detailtests/test_stdlib_os.py` covers
    separator, platform, cwd normalization, directory ordering, missing env,
    unset-missing, and case-sensitivity behavior.
  - Follow-up: file-system case sensitivity remains an explicitly host-owned
    property; future package tooling should rely on exact-case fixture paths or
    add a separate capability probe before enforcing case-folding rules.

## Planning notes

- [x] Verified all historical checklist entries below this section remain
  archived/completed and can stay unchanged.
- [x] Promoted a focused set of open tasks from the roadmap so the backlog has
  clear in-progress candidates again.

## Proposed next-cycle tasks (2026-06 draft)

The following items are intentionally left open (`- [ ]`) and are candidates
for triage into the next active timebox.

- [x] **Publish a language-server compatibility matrix per editor client**
  (Owner: Tooling)
  - Success: `docs/language_server_workflows.md` includes a matrix for VS Code,
    Neovim (LSP), and generic Language Server Protocol clients with supported
    capabilities (`hover`, `diagnostics`, `formatting`, `code actions`) and
    known caveats.
  - Notes: added the "Editor-client compatibility matrix" section and method-
    level caveats in `docs/language_server_workflows.md` covering VS Code,
    Neovim, and generic LSP client adapters.

- [x] **Add package lockfile reproducibility checks across platforms**
  (Owner: Ecosystem)
  - Success: A deterministic test verifies that the same `tiny.toml` generates
    identical lockfile content on Linux/macOS/Windows path conventions,
    including normalized separators and stable dependency ordering.
  - Notes: added `tests/detailtests/test_pkg_lockfile_reproducibility.py` and
    updated `src/tiny_pkg_resolution.py` to normalize dependency paths and
    sort dependency keys before lockfile rendering for stable output.

- [x] **Define interpreter/native parity gates for release candidates**
  (Owner: Runtime)
  - Success: `docs/release_candidate_checklist.md` adds explicit parity gates
    requiring key smoke programs to match output and error codes across
    interpreter, C backend, and native backend before release sign-off.
  - Notes: expanded `docs/release_candidate_checklist.md` with a CI parity gate,
    a required interpreter/C/native smoke scenario matrix, and a manual
    transcript-attachment requirement for release sign-off auditability.

- [x] **Add a stdlib API change budget for minor releases**
  (Owner: Language/Stdlib)
  - Success: `docs/versioning_deprecation_policy.md` defines a per-minor budget
    for additive vs. breaking stdlib changes and references the required
    migration-note template.
  - Notes: added the "Stdlib API change budget for minor releases" section to
    `docs/versioning_deprecation_policy.md`, including explicit additive/
    soft-breaking/hard-breaking limits and a required migration-note template
    tied to `docs/release_minor_upgrade_guides.md` and
    `docs/release_minor_guides/`.

## Open-task audit (2026-02-13)

- [x] Audited repository planning docs for unchecked checklist entries (`- [ ]`).
  - Result: no unchecked checklist tasks remain in `docs/` at audit time.
- [x] Promoted the next planning action for this cycle:
  - Run backlog triage for newly proposed items (owner assignment + sequencing) and either
    move accepted items into the refreshed near-term backlog or archive deferred items with rationale.

The active work items are tracked in the refreshed near-term backlog and the
sections below.

## Refreshed near-term backlog (published 2026-03-20)

Timebox: 2026-03-20 to 2026-05-01 (6 weeks).

1. **Refresh the roadmap with a concrete minor-release milestone** (Owner: Project Lead)
   - Success: `docs/roadmap_next.md` includes a dated milestone section with
     3-5 deliverables and cross-links to the corresponding backlog items.
2. **Expand module-resolution regression coverage for package workflows** (Owner: Ecosystem)
   - Success: Add edge-case tests for vendor cache + local override precedence,
     plus a short note in `docs/module_resolution_algorithm.md` describing the
     precedence order tested.
3. **Add LSP formatting-hook acceptance coverage** (Owner: Tooling)
   - Success: A new multi-file LSP test validates formatting hooks and documents
     the request/response shape in `docs/language_server_workflows.md`.
4. **Define a repeatable profiling capture workflow** (Owner: Runtime)
   - Success: `docs/performance_budgets_and_baselines.md` describes a step-by-step
     profiling capture flow and identifies the baseline artifacts to store.

### Concrete tasks derived from refreshed backlog

- [x] Add a dated 2026-05 planning milestone section to `docs/roadmap_next.md`
  with 3-5 deliverables and cross-links to refreshed backlog items.
  - Notes: added the "2026-05 minor-release planning checkpoint" section with
    four deliverables, explicit backlog references, and milestone exit criteria
    in `docs/roadmap_next.md`.

- [x] Expand module-resolution regression coverage for package workflows,
  including local override + vendor precedence edge cases, and document the
  tested precedence order in `docs/module_resolution_algorithm.md`.
  - Notes: added package precedence tests in
    `tests/detailtests/test_module_resolution_algorithm.py` and documented
    local-override → registry-vendor → git-vendor ordering in
    `docs/module_resolution_algorithm.md`.

- [x] Add LSP formatting-hook acceptance coverage with a multi-file project
  workflow and document the formatting/code-action request/response payloads
  in `docs/language_server_workflows.md`.
  - Notes: added multi-file formatting-hook acceptance assertions in
    `tests/detailtests/test_language_server_cli.py`
    (`test_cli_project_formatting_hook_matches_format_output`) and aligned the
    workflow documentation examples in `docs/language_server_workflows.md`.

- [x] Define a repeatable profiling capture workflow in
  `docs/performance_budgets_and_baselines.md` that includes baseline capture,
  environment metadata snapshots, artifact retention paths, and post-merge
  baseline tagging guidance.
  - Notes: expanded the profiling workflow into an explicit runbook with
    deterministic benchmark commands, required artifact layout under
    `artifacts/perf/<date>/raw`, canonical baseline update steps, and
    version-control tag conventions for later regression triage.

## Newly proposed backlog items (drafts)

The tasks below are newly formulated and meant to be triaged into the active
backlog once ownership and sequencing are confirmed.

1. ✅ **Ship a package publish dry-run workflow** (Owner: Ecosystem, Completed)
   - Success: `docs/package_manager_plan.md` documents a `tiny pkg publish --dry-run`
     workflow and `tools/tiny_pkg_publish.py` supports an explicit dry-run mode that
     emits the staged payload without network side effects.
   - Status: Completed via the concrete tasks below (`docs/package_manager_plan.md`,
     `tools/tiny_pkg_publish.py`, and `tests/detailtests/test_tiny_pkg_publish.py`).
2. ✅ **Document debugger trace workflows for async tasks** (Owner: Tooling, Completed)
   - Success: `docs/debugger_guide.md` adds a walkthrough for stepping through
     async tasks, including the expected output from `tiny debug trace` when
     multiple tasks are scheduled.
   - Status: Completed via the concrete task below (`docs/debugger_guide.md`).
3. ✅ **Add reproducible perf regression triage playbook** (Owner: Runtime, Completed)
   - Success: `docs/performance_budgets_and_baselines.md` includes a playbook
     for diffing baseline JSONs, capturing flamegraphs, and filing regression
     tickets with the required artifacts.
   - Status: Completed via the concrete task below
     (`docs/performance_budgets_and_baselines.md`).
4. ✅ **Define a module deprecation workflow for stdlib moves** (Owner: Language/Stdlib, Completed)
   - Success: `docs/versioning_deprecation_policy.md` includes a checklist for
     stdlib moves (announce, warn, provide alias, remove) and references the
     existing compatibility matrix.
   - Status: Completed via the concrete task below (`docs/versioning_deprecation_policy.md`).
5. ✅ **Define a Python-independent self-hosting compiler bootstrap path** (Owner: Compiler/Runtime, Completed)
   - Success: `docs/self_hosting_port_plan.md` documents a staged bootstrap
     strategy where TinyLanguage can compile TinyLanguage without a Python
     runtime dependency, using a minimal platform-specific seed executable per
     target OS as the initial trust anchor.
   - Status: Completed via the concrete task below
     (`docs/self_hosting_port_plan.md`).
6. ✅ **Define an executable optimization plan for native builds** (Owner: Runtime/Compiler, Completed)
   - Success: `docs/native_compiler.md` and `docs/runtime_performance_goals.md`
     include a prioritized optimization backlog for generated executables
     (LLVM pass tuning, opt-level defaults, profile-guided workflow) plus
     benchmark-based acceptance criteria.
   - Status: Completed via the concrete tasks below
     (`docs/native_compiler.md`, `docs/runtime_performance_goals.md`).

### Concrete tasks derived from the drafts

- [x] Add an async-task debugger trace walkthrough to `docs/debugger_guide.md`
  that includes setup steps, the `tiny debug trace` invocation, and expected
  output for multiple concurrently scheduled tasks.
  - Notes: `docs/debugger_guide.md` now includes a CLI-first walkthrough with
    a runnable async sample, breakpoint configuration, expected trace output,
    and interpretation guidance for two concurrently scheduled tasks.

- [x] Draft a `tiny pkg publish --dry-run` CLI spec section that enumerates inputs,
  outputs, and expected artifacts for review in `docs/package_manager_plan.md`.
- [x] Add a minimal dry-run execution path in `tools/tiny_pkg_publish.py` that
  serializes the payload to disk and returns a non-zero exit code when validation
  fails.
  - Follow-up: `tools/tiny_pkg_publish.py` now requires the explicit `--dry-run`
    flag and exits with code `2` when invoked without it, keeping behavior aligned
    with the documented `tiny pkg publish --dry-run` workflow.
- [x] Capture an async-task debugging transcript (commands + outputs) and embed
  it in `docs/debugger_guide.md` as a worked example.
- [x] Extend `docs/performance_budgets_and_baselines.md` with a checklist for
  capturing flamegraphs, tagging baseline snapshots, and filing regressions with
  links to artifacts.
- [x] Add a stdlib deprecation checklist entry to
  `docs/versioning_deprecation_policy.md`, including the expected warning
  timeline and aliasing strategy.
- [x] Finalize the `stdlib.yaml` scope decision and replace the placeholder
  stub behavior with a minimal JSON-compatible implementation (mapping lines +
  JSON literals), including executable tests and examples.
  - Notes: `stdlib/yaml.tiny` now supports parsing `key: value` mappings,
    JSON-style scalar/list/map literals, and `load`/`dump` round-trips;
    coverage lives in `tests/detailtests/test_stdlib_yaml.py` and examples in
    `docs/stdlib_examples.md`.
- [x] Add a self-hosting compiler bootstrap milestone to
  `docs/self_hosting_port_plan.md` that defines seed executable requirements
  (Windows/macOS/Linux), reproducible bootstrap steps, and parity validation
  gates between Python-hosted and Tiny-hosted compilation outputs.
  - Notes: added a dedicated milestone section with per-OS seed trust-anchor
    requirements, staged reproducible bootstrap flow, explicit parity gates,
    and milestone exit criteria in `docs/self_hosting_port_plan.md`.
- [x] Add an executable-optimization milestone to `docs/native_compiler.md`
  that defines default `--llvm-opt-level` / `--opt-level` profiles, optional
  profile-guided optimization capture steps, and required benchmark deltas
  before changing release defaults.
  - Notes: added a dedicated milestone section in `docs/native_compiler.md`
    with profile defaults (`dev`/`release`/`max`), an optional PGO workflow,
    and explicit benchmark/stability/reproducibility gates for default changes.
    Added a matching prioritized optimization backlog + acceptance criteria in
    `docs/runtime_performance_goals.md` to keep cross-doc ownership aligned.

## Near-term priorities (next 4-6 weeks)

Active items are tracked in the refreshed backlog above.

**Next milestone:** 2026-05 minor release planning checkpoint (roadmap refresh
with scoped deliverables and owners).

## Package tooling execution plan (proposed)

Concrete next steps derived from the package/module roadmap to move from
documentation into implementation.

- [x] Emit a vendor summary (`vendor/README.md`) during `tiny pkg vendor` for
  auditability (manifest hash + dependency list).
- [x] Add lockfile drift checks that fail `tiny pkg vendor` when
  `manifest_hash` does not match the current `tiny.toml`.
- [x] Add unit coverage for `tiny pkg vendor` readme output and lockfile drift
  validation.
- [x] Document the package CLI workflows in `docs/package_manager_plan.md` with
  the new vendor audit output and lockfile drift behavior.

## Proposed production-readiness tasks (draft for next planning cycle)

These are suggested tasks to move TinyLanguage from a capable prototype toward
a fully functional, production-ready language. They are intentionally concrete
and testable so they can be promoted into the formal backlog as needed.

### Language + runtime stability
- [x] Close remaining semantic ambiguities with executable spec tests (e.g.,
  numeric overflow, error propagation, evaluation order in edge cases).
  - Notes: added targeted spec tests for error propagation and overflow edges in
    `tests/detailtests/test_semantics_suite.py` and
    `tests/detailtests/test_number_overflow.py`.

### Package + module system (MVP → usable)
- [x] Add semver-aware dependency constraints and a minimal registry schema.
  - Notes: `src/tiny_pkg_resolution.py` parses SemVer constraints and resolves
    registry versions; `docs/package_manager_plan.md` documents the initial
    registry metadata schema with checksum fields.
- [x] Define a reproducible module-resolution algorithm shared by interpreter
  and native backends, including tests for edge cases.
  - Notes: documented the algorithm in `docs/module_resolution_algorithm.md`
    and added edge-case tests in
    `tests/detailtests/test_module_resolution_algorithm.py`.

### Standard library completeness
- [x] Ship “core IO” parity (`fs`, `path`, `process`, `env`, `time`) with
  parity tests against Python behavior.
  - Notes: added `stdlib.fs` wrapper plus parity coverage for `fs`, POSIX-style
    `path`, and `time`; existing `os` env tests cover `env`, and process parity
    remains scoped to the mock-backed API surface.
- [x] Expand networking and serialization modules (`http`, `json`, `toml`)
  with fuzzed round-trip tests.
  - Notes: added TOML stdlib wrapper, mock HTTP echo handling, and fuzzed
    round-trip tests for JSON/TOML/HTTP in the detail test suite.
- [x] Publish a stability/maturity tier for each stdlib module and a policy for
  deprecations.
  - Notes: maturity tiers and module status live in
    `docs/stdlib_compatibility.md`, with the deprecation policy defined in
    `docs/versioning_deprecation_policy.md`.

### Tooling + DX
- [x] Add end-to-end LSP acceptance tests for rename, references, and code
  actions across a multi-file project.
  - Notes: CLI tests now exercise `references`, `rename`, and `code-actions`
    against a multi-file project fixture in
    `tests/detailtests/test_language_server_cli.py`.
- [x] Provide a first-class formatter + lint baseline for CI and editor
  integration (single command to enforce).
  - Notes: `tools/format_lint_baseline.py` provides a unified formatter + lint
    runner with `--check`/`--apply` modes for CI and editor tasks.
- [x] Improve debugger parity (breakpoints, variable inspection, async tasks)
  with a canonical test suite.
  - Notes: added async breakpoint scope coverage to the debugger hook tests in
    `tests/detailtests/test_debugger_hooks.py` to validate spawned-task locals.

### Distribution + releases
- [x] Produce signed, reproducible release artifacts for all supported OSes
  and include SBOMs in release bundles.
- [x] Publish upgrade guides and automated migration tooling for each minor
  release.
  - Notes: added `docs/release_minor_upgrade_guides.md`, a migration recipe
    registry (`docs/release_minor_migration_recipes.json`), and the automation
    entry point `tools/release/prepare_minor_upgrade.py`.
- [x] Establish a release-candidate checklist that is run in CI.
  - Notes: added `docs/release_candidate_checklist.md`, a CI gate script in
    `tools/release/check_release_candidate_checklist.py`, and wired it into
    `.github/workflows/ci.yml`.

### Performance + reliability
- [x] Lock in performance budgets per backend and enforce regression alerts in
  CI with baseline snapshots.
  - Notes: baseline snapshot tracked in `benchmarks/performance_baselines.json`
    and enforced in CI via `tools/performance/check_performance_budgets.py`.
- [x] Expand fuzzing coverage (lexer/parser/runtime) and require nightly runs.
  - Notes: added lexer/parser fuzz coverage in
    `tests/detailtests/test_benchmark_and_fuzz.py` and scheduled nightly runs
    via `.github/workflows/nightly-fuzz.yml`.
- [x] Add stress tests for concurrency primitives and memory-pressure handling.
  - Notes: added stress coverage for spawn/join and repeated heap allocations in
    `tests/detailtests/test_concurrency.py`.

## Expansion roadmap follow-ups

- [x] Define the Julia subset target and list functions in `docs/julia_subset.md`.
  - Owner: Language/Stdlib
  - Success: Documented function list with examples and scope boundaries.
- [x] Implement `mean` + `std` in a new statistics module with tests.
  - Owner: Stdlib
  - Success: `stdlib/statistics.tiny` plus tests comparing outputs to Python/NumPy where feasible.
- [x] Expand parity tests for multi-line/nested error spans.
  - Owner: Tooling
  - Success: Regression suite verifies identical formatting for complex spans.
- [x] Add a regression matrix for self-hosting modules.
  - Owner: Tooling
  - Success: Documented matrix with last-verified versions and known deviations.

## Longer-term backlog (unprioritized)

- [x] Conformance + cross-backend parity suite expansion.
  - Added parity fixtures for function branching and looped arithmetic in
    `tests/parity/`.

## Open-task audit (2026-04-05)

- [x] Re-read all documentation checklists to identify the next unchecked work item and execute it to completion.
  - Result: no unchecked checklist items remain in `docs/` or in the root documentation task files (`documentation_tasks.md`).
  - Follow-up: kept the backlog in a fully closed state and recorded this verification pass so the next cycle can start by adding new scoped tasks instead of re-auditing historical ones.

## Open-task audit (2026-04-17)

- [x] Re-validated the documentation backlog to find the next unchecked documented task and execute it.
  - Result: there are still no unchecked checklist entries (`- [ ]`) in `docs/`, `documentation_tasks.md`, or `README.md`; the next actionable step is to add newly scoped tasks for the upcoming cycle before further execution work.
  - Follow-up: backlog remains intentionally closed; future "next open task" requests should begin by triaging and adding a new concrete unchecked item into `docs/open_tasks.md`.

## Open-task audit (2026-04-25)

- [x] Convert one documented package-manager open question into an implemented, test-backed decision.
  - Result: `tiny.lock` now persists an optional top-level `toolchain` constraint derived from `[package].tiny_language` in `tiny.toml`, and the behavior is covered by lockfile reproducibility tests.
  - Follow-up: keep the second package-manager open question (signed registry metadata) for the next planning cycle, because it depends on registry threat-model and deployment decisions.


## Priority execution update (2026-05-02, follow-up)

- [x] **Process highest-priority documented open question (package registry signing)** (Owner: Ecosystem)
  - Result: resolved the remaining package-manager open question in `docs/package_manager_plan.md` with a phased decision for metadata signing (v1.1 informational hashes, v1.2 optional verification, v1.3 required signatures for official channels).

## TinyCPU execution update (2026-08-03)

- [x] **AP 7: Maschinenformat und Tooling** (Owner: TinyCPU)
  - Result: froze the version-1 22-bit machine-word layout and opcode table,
    added a range-checking encoder/decoder that emits Logisim ROM images and
    listings, and loaded the generated AP 5 countdown image into the circuit.
  - Verification: instruction-wide roundtrip tests and artifact/circuit parity
    tests protect the encoding contract; AP 8 remains the next work package.

## TinyCPU top-level integration update (2026-08-09)

- [x] **Integrate the unary `NOT` accumulator-write control** (Owner: TinyCPU)
  - Result: routed `FetchDecodeControls.NOT` through a dedicated second-stage
    `ACC_WRITE_REQUEST` OR gate, together with the existing 32-input arithmetic
    family aggregator, so only the combined output drives `Datapath.ACC_LOAD`.
  - Verification: structural regression coverage proves that `NOT` remains
    isolated from sibling decoder outputs and that the combined write request
    reaches the accumulator without touching `DATA_IN`; `INPUT` is the next
    accumulator-writing top-level control.
