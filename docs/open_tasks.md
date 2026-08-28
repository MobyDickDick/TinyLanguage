# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

- [x] **AP 13: Freeze the TinyCPU 1.0 release contract**
  (Owner: TinyCPU/Release; completed 2026-08-28)
  - Scope: define and validate the machine-readable product boundary before any
    archive or release candidate is built.
  - Result: `tinycpu-release-v1.json` freezes the hardware and machine profiles,
    runtime versions, AP-12 evidence schema, and supported CLI help boundary;
    the 1.x compatibility policy separates those interfaces from diagnostics.
  - Verification: focused negative cases reject missing and contradictory
    metadata, while the normal checkout verifier cross-checks every source.
  - Follow-ups: AP 14 (reproducible distribution) is complete; AP 15
    (qualification and publication) is now active.

- [x] **AP 14: Build a reproducible TinyCPU distribution**
  (Owner: TinyCPU/Release; completed 2026-08-28)
  - Scope: build source and simulator-ready archives from the frozen AP-13
    contract without modifying the checkout.
  - Deliverables: one release command, canonical path/size/SHA-256 inventories,
    the declared circuit, tools, example, documentation, license, and retained
    AP-12 evidence, plus an offline bundle verifier.
  - Acceptance: two clean builds are identical; missing, extra, symlinked, or
    digest-mismatched files are rejected; extracted verification succeeds
    outside the repository.
  - Result: `tools/tiny_cpu_distribution.py` creates deterministic source and
    simulator archives, embeds canonical inventories and an offline verifier,
    and retains only passed, internally consistent AP-12 evidence.
  - Verification: focused tests rebuild both artifacts twice byte-for-byte,
    verify an extracted bundle outside the checkout, and exercise every
    required rejection class. AP 15 is now active.

- [x] **AP 15: Qualify and publish TinyCPU 1.0**
  (Owner: TinyCPU/Release; completed 2026-08-28)
  - Scope: qualify the exact AP-14 artifacts with the mandatory AP-12 gate and
    a clean-room countdown run, then publish those unchanged artifacts.
  - Deliverables: release-candidate checklist, release notes and supported
    limitations, authenticated checksums, and the `tinycpu-v1.0.0` tag.
  - Acceptance: every result names the same commit and artifact digests, and
    the published archives are byte-for-byte the qualified candidate.
  - Result: `tools/tiny_cpu_qualification.py` verifies AP-14 archives outside
    the checkout, runs the countdown in a clean room, stages unchanged archive
    bytes, records the commit and digests, and signs the canonical checksum
    list. The release notes freeze the support boundary and authenticated
    `tinycpu-v1.0.0` publication procedure.
  - Verification: focused tests cover the complete checkout and AP-12 gates, a
    successful signed qualification, candidate/publication byte identity,
    wrong or malformed commits, and post-signing archive or report tampering.

- [x] **Finish making the TinyCPU trace regression redraw-aware**
  (Owner: TinyCPU/Testing; completed 2026-08-27)
  - Scope: execute the next bounded maintenance package after the integration
    sheet redraw by auditing the trace regression for drawing coordinates that
    still represented generated-symbol ports rather than electrical identity.
  - Cause: the trace probes and halt outputs were resolved by labels after the
    redraw, but the `FetchDecodeControls.PRINT` assertion still froze its old
    top-level coordinate and would reject an electrically equivalent move.
  - Result: the regression now derives the generated decoder-control output from
    the named subcircuit pin and instance position before checking its route to
    the named top-level output. Genuine disconnects remain failures while
    coordinate-only redraws no longer require weakening the contract.
  - Verification: the focused trace-runner and Logisim topology suites pass
    against the maintained circuit.

- [x] **Confirm the TinyCPU work-package boundary after task-log repair**
  (Owner: TinyCPU/Documentation; completed 2026-08-27)
  - Scope: answer the request for the next documented TinyCPU package by
    rechecking the repaired active-task boundary, the detailed AP inventory,
    and the expansion roadmap before touching the accepted circuit.
  - Result: the detailed package table and status checklist still close the
    same AP 1 through AP 12 inventory, the active history contains no unchecked
    TinyCPU package, and the expansion roadmap explicitly scopes no successor.
    Therefore there is no documented implementation package to execute and no
    hardware change is warranted.
  - Follow-up contract: a future TinyCPU package must first be recorded as a
    bounded, unchecked item with acceptance criteria; completed maintenance
    history and descriptive implementation notes do not create new scope.
  - Verification: the roadmap-consistency regression derives the complete
    package inventory and empty active backlog instead of treating the newest
    completed maintenance entry as an implicit successor package.

- [x] **Repair the TinyCPU active-task boundary**
  (Owner: TinyCPU/Documentation; completed 2026-08-27)
  - Scope: execute the next bounded documentation-maintenance package by
    checking the active-task heading after the completed decoder-output audit
    was removed from the current history.
  - Cause: that cleanup left the final wrapped line of the removed package
    between the heading and the next checklist entry, so the task log started
    with an orphaned sentence rather than a complete work package.
  - Result: the orphaned line is removed and the current history again begins
    with a complete, attributable TinyCPU package; the accepted AP-1-to-AP-12
    hardware boundary remains unchanged.
  - Verification: the roadmap-consistency regression requires the first
    nonblank content below `Current tasks` to be a complete checklist entry and
    rejects an indented prose fragment at that boundary.

- [x] **Connect the TinyCPU `JUMP_NOT_ZERO` decoder lane**
  (Owner: TinyCPU/Hardware; completed 2026-08-27)
  - Scope: execute the next bounded schematic-maintenance package by promoting
    the documented open opcode-36 decoder line to a dedicated
    `FetchDecodeControls.JUMP_NOT_ZERO` output and routing it to
    `FetchDecode.DEC_JUMP_NOT_ZERO`.
  - Result: opcode 36 now has its own control pin and a visible top-level route;
    the neighboring `JUMP_ZERO` and `JUMP_NEGATIVE` lanes remain isolated.
  - Verification: focused topology regressions trace both halves of the route,
    and the extracted diagnostic is kept byte-for-byte aligned with the
    maintained circuit.

- [x] **Validate the TinyCPU blind-wire cleanup**
  (Owner: TinyCPU/Hardware; completed 2026-08-27)
  - Scope: execute the next bounded schematic-maintenance package by checking
    the removed `FetchDecodeControls` wire from `(520,390)` to `(680,390)`
    against the accepted electrical and topology contracts.
  - Result: the disconnected horizontal spur remains removed; the surrounding
    decoder-control routes and the completed AP-12 boundary are unchanged.
  - Verification: the extracted `FetchDecodeControls` diagnostic was refreshed
    and the focused Logisim regression suite now rejects reintroducing this
    exact blind wire or allowing the checked-in diagnostic to drift.

- [x] **Align the highlighted TinyCPU completion heading**
  (Owner: TinyCPU/Documentation; completed 2026-08-27)
  - Scope: execute the next documentation-maintenance package by comparing the
    separately highlighted completed package with the canonical package table
    and status checklist aligned by the preceding package.
  - Result: the completion heading now identifies AP 12 by both its number and
    canonical `Hardware-Abschluss` title instead of reintroducing a third,
    titleless package reference.
  - Verification: the roadmap-consistency regression parses the highlighted
    package and requires it to equal the final canonical table entry.

- [x] **Cross-check the TinyCPU package titles**
  (Owner: TinyCPU/Documentation; completed 2026-08-27)
  - Scope: execute the next documentation-maintenance package by comparing the
    names in the twelve-package definition table with the completed status
    checklist, after the preceding package froze their numeric inventory.
  - Result: every AP 1 through AP 12 status entry now repeats its canonical
    table title; the previously titleless AP 10 and AP 11 entries and the
    shortened AP 12 entry no longer leave two competing package inventories.
  - Verification: the roadmap-consistency regression parses package numbers and
    titles from both detailed inventories and requires exact ordered equality.

- [x] **Cross-check the complete TinyCPU package inventory**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documentation-maintenance package by comparing the
    twelve package definitions in the detailed roadmap table with its completed
    status checklist and the high-level expansion boundary.
  - Result: the package table and status checklist both enumerate exactly
    AP 1 through AP 12, while the expansion roadmap continues to expose no
    separately scoped next package; no circuit change is warranted.
  - Verification: the roadmap-consistency regression parses both detailed
    inventories, rejects missing, duplicate, or extra package numbers, and
    requires their equality before accepting the no-work boundary.

- [x] **Align the complete TinyCPU boundary in the expansion roadmap**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documentation-maintenance package by comparing the
    high-level expansion roadmap with the complete AP 1 through AP 12 inventory
    already frozen in the detailed roadmap.
  - Cause: the expansion roadmap described only the electrical AP 9 through
    AP 12 subset as its completed boundary and referred to the checked-off task
    log as active maintenance history.
  - Result: the high-level boundary now explicitly closes AP 1 through AP 12,
    distinguishes the AP-1-to-AP-8 baseline from the AP-9-to-AP-12 electrical
    gates, and describes the task log as completed maintenance history.
  - Verification: the roadmap-consistency regression requires the complete
    boundary and rejects the superseded AP-9-to-AP-12-only wording.

- [x] **Freeze the complete TinyCPU work-package boundary**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: harden the no-next-package decision by checking the complete
    documented AP 1 through AP 12 inventory, rather than only the later
    electrical AP 9 through AP 12 subset.
  - Result: all twelve roadmap packages remain explicitly checked off and no
    new circuit scope is inferred from completed implementation history.
  - Verification: the roadmap-consistency regression now enumerates AP 1
    through AP 12 before accepting the expansion roadmap's empty next-package
    boundary.

- [x] **Re-validate the TinyCPU work-package boundary**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: answer the request for the next documented TinyCPU package by
    auditing the active backlog, detailed hardware roadmap, and expansion
    roadmap before changing the accepted circuit.
  - Result: AP 1 through AP 12 and every explicitly bounded TinyCPU follow-up
    remain complete; there is no unchecked TinyCPU package to implement.
    Consequently this audit makes no circuit change and does not invent scope
    from historical implementation notes.
  - Follow-up contract: new TinyCPU work must first be added here as a bounded,
    unchecked package with acceptance criteria, as required by the expansion
    roadmap.
  - Verification: the roadmap-consistency regression checks the empty active
    TinyCPU backlog and freezes this explicit no-work boundary.

- [x] **Reconcile the TinyCPU completeness documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: verify the user's apparent open pins and potentially missing
    instructions against the maintained circuit, machine table, electrical
    matrix, and roadmap, then execute the next documentation-maintenance item.
  - Cause: the user guide still presented the accepted construction sequence
    as imperative future work, while AP 1 still referred to missing wiring and
    the roadmap labelled completed integration as a follow-up.
  - Result: the guide now records `TinyCPUMain: connected`, all 50 versioned
    opcodes as electrically covered, and the construction list as acceptance
    history; the detailed roadmap marks baseline and top-level integration as
    completed without claiming that visual wire crossings are junctions.
  - Verification: the roadmap-consistency regression compares the ISA and
    machine opcode inventories and freezes the reconciled completion wording.

- [x] **Reconcile the TinyCPU inspector-boundary documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documentation-maintenance package after retiring
    the incremental-build exception by checking the remaining inspector note
    against the accepted circuit and its current verification boundaries.
  - Cause: the reference still claimed that the maintained top-level blocks
    report `INCOMPLETE`/`unconnected`, although the inspector reports
    `TinyCPUMain: connected`; it also left the generic connectivity diagnostic
    insufficiently distinguished from focused topology and simulator proof.
  - Result: the reference now records the current connected status, treats a
    future incomplete report as a maintenance failure, and explicitly states
    why connected pins alone do not constitute electrical acceptance.
  - Verification: the roadmap-consistency regression freezes the current
    inspector status and its boundary to topology tests and AP-12 acceptance.

- [x] **Retire the TinyCPU incremental-build verification exception**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documentation-maintenance package after retiring
    the top-level worksheet by reconciling its remaining per-net build and
    verification instructions with the accepted AP-12 circuit boundary.
  - Cause: the reference still allowed `TinyCPU: INCOMPLETE` during an implied
    incremental build and offered an unrestricted worksheet even though no
    further construction package is scoped.
  - Result: the reference now reserves its change record for previously scoped
    maintenance packages, requires contract mismatches to become explicit
    work, and rejects every incomplete or electrically invalid maintained
    circuit.
  - Verification: the roadmap-consistency regression rejects the historical
    build exception and freezes the bounded-maintenance wording.

- [x] **Retire the completed TinyCPU top-level build worksheet**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documentation-maintenance package after the halt
    reconciliation by checking whether the top-level template still presented
    the now-complete steps 0 through 11 as future construction work.
  - Cause: the heading and introduction continued to call the document a
    worksheet for extending the overview even though every row now records an
    accepted electrical boundary and no new TinyCPU package is scoped.
  - Result: the document is now an integration reference, explicitly records
    the table as completed acceptance history, and reserves future circuit
    changes for separately scoped maintenance packages.
  - Verification: the roadmap-consistency regression rejects the obsolete
    build-worksheet title and freezes the completed-step statement.

- [x] **Reconcile the TinyCPU halt-boundary follow-up documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documented TinyCPU integration package after the
    error-register reconciliation by checking the final halt row against the
    maintained decoded controls, top-level pins, and integration-trace names.
  - Cause: the template still described anonymous normal and error sources and
    named only the trace fields as top-level targets, obscuring the circuit's
    actual `HALTED` and `HALTED_WITH_ERROR` output boundary.
  - Result: the template now records the direct, isolated `HALT` and
    `HALT_ERROR` decode routes, their physical output pins, their trace-field
    mappings, and the deliberate absence of a shared halt-state OR gate.
  - Verification: the roadmap-consistency regression freezes both halt routes
    and rejects the obsolete generic source description.

- [x] **Reconcile the TinyCPU error-register follow-up documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documented TinyCPU integration package after the
    status reconciliation by checking the error row against the maintained
    decoded controls, operation/address errors, and `ErrorFlags` boundary.
  - Cause: the template still reduced the completed error integration to
    generic set signals and a future sticky-behavior check, obscuring which
    sources are decoded controls and which are derived execution errors.
  - Result: the template now records `CLEAR_ERROR`, decoded illegal-opcode and
    input errors, the four derived execution-error routes, and the six
    set-dominant sticky outputs as the completed error-register boundary.
  - Verification: the roadmap-consistency regression freezes the named error
    sources, outputs, and priority rule and rejects the obsolete generic row.

- [x] **Reconcile the TinyCPU status follow-up documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documented TinyCPU integration package after the
    accumulator-data reconciliation by checking the status row and endpoint
    table against the extracted `Operations` and `EffectiveAddress` boundaries.
  - Cause: the template still described generic validity and error-logic
    destinations instead of the maintained result-valid, branch-status, and
    operation/address error routes.
  - Result: the template now records the single `Operations.RESULT_IS_VALID`
    load-validity route, the zero-derived `FetchDecode.NOT_ZERO` condition,
    and the distinct overflow, divide-by-zero, invalid-operand, and address
    error boundaries.
  - Verification: the roadmap-consistency regression freezes the completed
    status endpoints and rejects the obsolete generic status description.

- [x] **Reconcile the TinyCPU accumulator-data follow-up documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documented TinyCPU integration package after the
    address-and-memory reconciliation by checking the data-bus row and its
    endpoint table against the extracted `Operations` boundary.
  - Cause: the template still described the superseded top-level
    `ACC_DATA_SELECT`, `ACC_NOT_SELECT`, and `ACC_INPUT_SELECT` chain and listed
    decoder outputs as the source of the accumulator write request.
  - Result: the template now records the maintained operand, memory, and
    accumulator inputs of `Operations`, its single selected result into
    `Datapath.DATA_IN`, and the canonical `DecodeSignals.ACC_WRITE_REQUEST`
    control boundary.
  - Verification: the roadmap-consistency regression freezes the completed
    data boundary and rejects the obsolete selector and request names.

- [x] **Reconcile the TinyCPU address-and-memory-control follow-up documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next documented TinyCPU integration package after the
    accumulator-control reconciliation by checking the address-control,
    memory-control, and address-bus rows of the top-level wiring template.
  - Cause: the rows still used prospective drawing instructions even though
    the maintained circuit already selects one effective address for direct,
    address-register, and address-register-plus-offset modes and connects that
    selection to both data and validity RAM.
  - Result: the template now records the completed effective-address boundary,
    accumulator-backed store controls, and shared RAM address bus, while
    retaining their electrical acceptance rules.
  - Verification: the roadmap-consistency regression freezes the three
    completed boundaries and rejects the obsolete prospective instructions.

- [x] **Reconcile the TinyCPU datapath-control follow-up documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next explicitly documented TinyCPU follow-up by checking
    the roadmap and top-level integration template against the completed
    accumulator-control boundary.
  - Cause: both documents still said that datapath control nets were the next
    integration step even though `DecodeSignals.ACC_WRITE_REQUEST` already
    combines every accumulator-writing instruction family and drives the
    maintained `Datapath.ACC_LOAD` boundary.
  - Result: the historical roadmap and integration table now record that step
    as completed instead of advertising it as future work.
  - Verification: the roadmap-consistency regression freezes the completed
    datapath-control wording and rejects both obsolete follow-up markers.

- [x] **Reconcile the TinyCPU OR integration documentation**
  (Owner: TinyCPU/Documentation; completed 2026-08-26)
  - Scope: execute the next explicitly documented TinyCPU follow-up by checking
    the bitwise-OR extraction contract against the maintained `Operations`
    sheet and the completed integration history.
  - Cause: the hardware README still called OR integration a separate
    follow-up even though `OrSubCircuit` is already instantiated and connected
    to the shared result, validity, and activity trees.
  - Result: the extraction contract now describes the integrated boundary and
    no longer advertises the completed package as future work.
  - Verification: the roadmap-consistency regression freezes the completed OR
    integration wording and rejects the obsolete follow-up marker.

- [x] **Accept the latest TinyCPU FetchDecode layout**
  (Owner: TinyCPU/Hardware; completed 2026-08-26)
  - Scope: retain the latest manual `FetchDecode` redraw while checking that
    the sequential-PC, jump-target, jump-control, selected-PC, and range-error
    routes are still electrically correct.
  - Result: the adjusted selector and gates remain authoritative; the focused
    topology regressions now follow their real terminals and the checkout gate
    validates the selector at its new position instead of restoring the old
    drawing.
  - Verification: the regenerated `FetchDecode` diagnostic is structurally
    identical to the maintained sheet, while pairwise selector isolation and
    the comparator-greater error route remain covered.

- [x] **Freeze the TinyCPU accumulator write-request causes**
  (Owner: TinyCPU/Hardware; completed 2026-08-26)
  - Scope: close the stale pending integration check left behind when the
    accumulator write-request gates moved from `TinyCPUMain` into
    `DecodeSignals`.
  - Risk: the canonical public output name alone did not prove that the family
    request, `NOT`, and `INPUT` occupied three electrically independent inputs;
    a short between causes could write the accumulator for the wrong opcode.
  - Result: the focused topology regression now follows the maintained
    `DecodeSignals` boundary, proves one distinct aggregator input per cause,
    rejects cause-to-cause and input-to-output bypasses, and follows the
    aggregator output to the canonical `ACC_WRITE_REQUEST` pin.
  - Verification: the formerly expected-failing top-level test is now an
    active regression over the extracted decode sheet.

- [x] **Canonicalize the TinyCPU decode-request interface**
  (Owner: TinyCPU/Hardware; completed 2026-08-25)
  - Scope: triage the next bounded maintenance package after the closed
    electrical roadmap by auditing the newly extracted `DecodeSignals` output
    boundary.
  - Cause: the two public accumulator-request pins were saved as
    `ACC_MEMORY_REQUESST` and `ACCC_WRITE_REQUEST`, while the architecture
    documentation already specified the canonical singular spellings.
  - Result: `DecodeSignals` now exports `ACC_MEMORY_REQUEST` and
    `ACC_WRITE_REQUEST`; the maintained top-level write route follows the
    corrected interface name without changing the pin locations or wiring. The
    internal three-input OR gate is uniquely labelled `ACC_WRITE_AGGREGATOR`,
    so it cannot collide with the public output pin.
  - Verification: focused structural regressions freeze the complete public
    output-label set, require the uniquely named aggregator, and resolve the
    corrected accumulator-write pin through the subcircuit boundary.

- [x] **Enforce ASCII semantics for portable regex escapes**
  (Owner: Language/Stdlib; completed 2026-08-25)
  - Scope: close the Phase 2 determinism gap between the documented ASCII-only
    `\\d`, `\\w`, and `\\s` escapes and Python's default Unicode regex mode.
  - Result: the runtime now compiles the supported regex subset in explicit
    ASCII mode without restricting Unicode literals, classes, or wildcards.
  - Verification: the focused stdlib regression distinguishes ASCII from
    Arabic-Indic digits, accented word characters, and non-breaking spaces
    while retaining Unicode wildcard behavior.

- [x] **Complete TinyCPU next-PC selector pairwise isolation coverage**
  (Owner: TinyCPU/Hardware; completed 2026-08-25)
  - Scope: close the remaining assertion gap in the documented four-boundary
    `NEXT_PC` isolation contract.
  - Risk: the topology regression rejected five of the six possible terminal
    pairs, but did not explicitly reject a short between the select input and
    the selected output.
  - Result: all six pairwise combinations of the sequential-PC, jump-target,
    jump-control, and selected-output nets are now proven electrically
    isolated outside the multiplexer.
  - Verification: the focused jump topology regression additionally rejects
    reachability between the `JNZ_TAKEN` selector input and `NEXT_PC` output.

- [x] **Freeze TinyCPU next-PC selector net isolation**
  (Owner: TinyCPU/Hardware; completed 2026-08-25)
  - Scope: triage the next bounded package after restoring the jump operand by
    protecting all four electrical boundaries of the `NEXT_PC` selector.
  - Risk: simple reachability checks proved that each source reached a selector
    terminal, but did not reject a future short between the sequential-PC,
    jump-target, jump-control, or selected-output nets.
  - Result: the focused topology regression fixes the selector at its maintained
    location and proves that both data inputs, the select input, and the output
    remain mutually isolated outside the multiplexer.
  - Verification: the jump topology test continues to prove every required
    route while explicitly rejecting data-to-data, control-to-data, and
    output-to-input bypasses.

- [x] **Freeze the restored TinyCPU jump-operand route**
  (Owner: TinyCPU/Hardware; completed 2026-08-25)
  - Scope: triage the first concrete package after the intentionally closed
    backlog by protecting the repaired `FetchDecode` jump-target connection
    from another schematic adjustment.
  - Cause: the encoded instruction operand had been routed to an empty row at
    `y=610` instead of the splitter output at `y=580`, so a taken jump could
    not supply its target to the `NEXT_PC` selector.
  - Result: the instruction operand again reaches the jump-target selector on
    the maintained route, while the stale disconnected route remains absent.
  - Verification: the focused topology regression now freezes both segments
    of the repaired route, rejects both stale segments, and proves electrical
    reachability from the instruction operand to the `NEXT_PC` data input.

- [x] **Expose a directory-scoped file-system case-sensitivity probe**
  (Owner: Language/Stdlib; completed 2026-08-25)
  - Scope: promote the deferred `stdlib.os` package-tooling capability question
    into a bounded API instead of inferring file-system behavior from the host
    platform.
  - Result: `os.filesystem_case_sensitive(path)` performs a cleanup-safe probe
    in an existing writable directory, while the portability contract keeps
    exact-case paths as the rule for read-only tooling.
  - Verification: the stdlib regression compares the Tiny result with an
    independent host probe and proves that no probe file remains afterward.

- [x] **Restore TinyCPU electrical contracts after the latest schematic adjustment**
  (Owner: TinyCPU/Hardware; completed 2026-08-25)
  - Cause: the latest Logisim save reset explicit component attributes in
    `FetchDecode` and `Operations` and removed the two final XOR input segments.
    That disabled PC advancement and immediate-value validity, made stable
    topology labels unavailable, and disconnected both XOR operands.
  - Result: the maintained circuit again carries the documented constant values,
    widths, splitter metadata, and selector/range labels; both XOR inputs are
    electrically connected. The derived leaf diagnostics have been regenerated
    from the repaired authoritative project.
  - Verification: the focused circuit, topology, extraction, and launcher tests
    accept the restored project and its reproducible diagnostic leaves.

- [x] **Reconcile stale TinyCPU follow-up notes with the completed hardware gate**
  (Owner: TinyCPU/Tooling; completed 2026-08-25)
  - Cause: several narrative sections still described the encoder, electrical
    integration trace, and AP-5 loop repair as future or outstanding work even
    though AP 7, AP 10, and AP 12 are accepted.
  - Result: the user guide now documents the versioned 22-bit machine format,
    and historical hardware notes identify those integration findings as
    resolved instead of presenting them as open follow-ups.
  - Verification: the roadmap-consistency regression rejects both an unchecked
    TinyCPU entry and the superseded future-work wording while the expansion
    roadmap states that no new package is currently scoped.

- [x] **Restore TinyCPU electrical contracts after the latest schematic adjustment**
  (Owner: TinyCPU/Hardware)
  - Cause: the latest manual `FetchDecode` and `Operations` adjustment retained
    the intended component positions and routes but reset explicit constant
    values, widths, splitter metadata, and stable selector/range labels to
    Logisim defaults.
  - Result: the adjusted drawing remains authoritative while the PC enable and
    increment constants, `PC_ADDRESS`, `NEXT_PC`, `PC_RANGE`, immediate-valid
    source, and accumulator result selectors again carry their documented
    electrical attributes.
  - Verification: focused topology tests resolve the restored labels and
    values, and regenerated leaf diagnostics reproduce the maintained project
    byte-for-structure rather than preserving the stale pre-adjustment sheets.

- [x] **Keep autonomous trace probes attached after TinyCPUMain redraws**
  (Owner: TinyCPU/Tooling)
  - Cause: the AP-5 clock probe used a fixed coordinate from the previous
    `TinyCPUMain` layout. Moving the external clock route left that temporary
    probe on empty canvas even though the maintained circuit remained wired.
  - Result: the trace harness now derives the clock tap from the wire adjacent
    to the labelled `CLK` input and resolves the opcode tap from the maintained
    22-bit splitter. Missing or ambiguous contacts fail before Logisim starts.
  - Verification: the harness regression confirms that both generated source
    tunnels occupy real endpoints or junctions in the maintained circuit.

- [x] **Restore electrical attributes after the TinyCPU schematic redraw**
  (Owner: TinyCPU/Hardware)
  - Cause: moving components in Logisim removed explicit values, widths, and
    stable labels from the fetch/decode and accumulator-result boundaries.
    Default-valued constants disabled the program counter and invalidated
    immediate loads, while unnamed components made the electrical contracts
    impossible to audit reliably.
  - Result: the moved components retain their intended layout and once again
    carry the asserted PC constants, splitter and selector labels, range-check
    label, and immediate-valid constant.
  - Verification: focused topology regressions resolve the components by their
    stable labels and confirm the configured values, widths, and complete
    electrical routes after the redraw.

- [x] **Preserve Logisim attributes while extracting leaf projects**
  (Owner: TinyCPU/Tooling)
  - Result: extraction deep-copies each complete XML subtree and verifies a
    recursive signature before serialization, including nested electrical
    attributes such as constant values, widths, and labels.
  - Boundary: this package deliberately leaves the maintained TinyCPU circuit
    and its JNZ routing unchanged, avoiding a stale schematic patch that could
    reintroduce a second `INVERT_ZERO_FOR_JNZ` during integration.
  - Verification: the extracted `FetchDecode` diagnostic must reproduce the
    checked-in sheet and retain the configured constants, `NEXT_PC`, and
    `PC_RANGE` attributes.

- [x] **Drive TinyCPU's not-zero jump condition from the accumulator status**
  (Owner: TinyCPU/Hardware)
  - Cause: `Datapath.ZERO` and `FetchDecode.NOT_ZERO` were both electrically
    isolated at the integration boundary. The decoder could recognize opcode
    36, but `JNZ_TAKEN` had no defined accumulator condition and the AP-5
    countdown could not implement its documented taken/taken/untaken sequence.
  - Result: a named inverter derives `NOT_ZERO` from the accumulator's zero
    flag and supplies the fetch block through one documented tunnel pair.
  - Routing exception: the status source and consumer lie in separate enclosed
    top-level wiring regions. A direct route would cross the clock, reset,
    address, and data nets, so this pair is the bounded exception allowed by
    the hardware routing policy.
  - Verification: a focused topology regression freezes the status source,
    inversion, two tunnel endpoints, and the receiving fetch input.

- [x] **Align TinyCPU terminal controls with their machine opcodes**
  (Owner: TinyCPU/Hardware)
  - Cause: the symbolic decoder-lane table assigned `JUMP_NEGATIVE` through
    `HALT_ERROR` one lane too early after the separately gated
    `JUMP_NOT_ZERO`. The control sheet followed that table, so opcode 44
    (`HALT`) electrically asserted `HALT_ERROR` and ended the AP-5 trace after
    eight edges with the wrong outcome.
  - Result: all affected controls now use their versioned machine-opcode lanes;
    in particular, opcode 44 reaches `HALT` and opcode 45 reaches
    `HALT_ERROR` on distinct nets.
  - Verification: a focused regression equates every documented decoder lane
    with `OPCODES`; the real simulator now reports normal rather than error
    halt. Its separately visible untaken-loop mismatch keeps the complete
    AP-12 gate pending.

- [x] **Keep store and address-register controls out of TinyCPU accumulator writes**
  (Owner: TinyCPU/Hardware)
  - Cause: `DecodeSignals.ACC_LOAD_REQUEST` consumed the first 32 decoder
    outputs, although only its first 28 outputs are accumulator-producing load
    and arithmetic families. The following three `STORE_*` controls and
    `LOAD_ADDRESS_REGISTER*` controls therefore reloaded the accumulator with
    the unrelated default result.
  - Result: the family request now has exactly 28 isolated inputs. Store and
    address-register instructions retain the accumulator while continuing to
    perform their own state changes.
  - Verification: a focused topology regression freezes both the included and
    excluded decoder ranges. The real AP-5 trace now preserves `-1` and `3`
    across their stores and no longer raises the former spurious `INV` flag.
  - Boundary: the trace now exposes a separate effective-memory-address and
    halt-outcome mismatch; the complete AP-12 gate remains pending.

- [x] **Preserve TinyCPU immediate values at the accumulator boundary**
  (Owner: TinyCPU/Hardware)
  - Cause: the extracted `Operations` sheet exported the OR-combined arithmetic
    result unconditionally. During `LOAD_CONST`, every arithmetic branch is
    inactive, so the accumulator received `0 INVALID` instead of the encoded
    immediate value and the following store raised `INV`.
  - Result: explicit result and validity selectors now use the instruction
    operand and valid constant outside active ALU/NOT cycles, while preserving
    the operation result and its computed validity during active operations.
  - Verification: the structural inspector accepts the completed sheet, a
    focused topology regression freezes both selector contracts, and the real
    Logisim AP-5 trace now visibly carries `ffff` and `0003` across the repaired
    boundary before reaching the separately pending memory/print integration
    mismatch.
  - Boundary: this package repairs only the first state boundary identified by
    the electrical trace; it does not claim that the complete AP-12 gate passes.

- [x] **Port statically approved quarantined sources to TinyLanguage**
  (Owner: Tooling/Program Generator)
  - Scope: execute the next pipeline stage in `docs/tiny_program_daemon.md`
    without weakening the quarantine or executing third-party source.
  - Result: the automatic porter revalidates provenance and the exact passing
    scan report, translates only the supported Python IR subset (or copies
    approved Tiny text), and atomically emits a hashed, versioned audit record.
  - Boundary: every result is marked `ported-unexecuted`; only the separate
    sandbox-test stage may evaluate it.

- [x] **Expose the first undefined TinyCPU fetch/decode boundary**
  (Owner: TinyCPU/Hardware)
  - Result: temporary electrical harnesses now export the 12-bit PC and 22-bit
    ROM opcode alongside the acceptance pins. The table adapter stops at the
    first `U`, `E`, or `X` and identifies whether undefined state is already
    present at the PC or first appears at the ROM output.
  - Boundary: this deliberately replaces further coordinate guesses with
    retained simulator evidence. The probes exist only in temporary projects
    and do not change the maintained `TinyCPUMain` interface.

- [x] **Remove TinyCPU signed-arithmetic bus conflicts**
  (Owner: TinyCPU/Hardware)
  - Cause: the sign-bit splitters in the `ADD`, `SUB`, and `MUL` arithmetic
    sheets were placed inline. Their 15-bit magnitude outputs therefore joined
    the original 16-bit operands and results, which Logisim reported as `E`
    values and which then contaminated the merged top-level result bus.
  - Result: every word-sized route now branches before its sign splitter. The
    independent 16-bit operand/result path bypasses the 15-bit terminal while
    the existing overflow logic retains its sign and magnitude taps.
  - Verification: the netlist inspector accepts all three arithmetic sheets,
    and a focused electrical-topology regression freezes both the word routes
    and their isolation from each 15-bit splitter output.
  - Additional repair: the `FetchDecode` ROM route now starts at the actual
    Logisim-evolution data terminal `(750,460)` and feeds both `OPCODE` and the
    instruction-field splitter; the previously documented `(550,410)` point is
    empty drawing space rather than a component contact.
  - Clock repair: `ErrorFlags.CLK` now belongs to the shared external clock net.
    It was incorrectly wired to `Datapath.ACC_VALID_OUT`, which propagated
    undefined validity into the sticky-error state and left observed controls
    at `U` even while the external clock was toggling.
    The same audit found the `AddressPath.CLK` terminal completely unwired; it
    now joins the shared clock as well, so the address register can leave its
    undefined startup state on the first accepted edge.
  - Compatibility correction: local `PowerOnReset` components were replaced
    by portable inactive constants because unsupported Logisim installations
    reject all four affected sheets while loading the file. This keeps every
    register reset terminal at a defined logic level; the checked-in PC remains
    controlled by the explicit external `RESET` input. The pinned acceptance
    harness still supplies its startup pulse in a temporary copy, without
    persisting a version-specific component in the user-facing file.

- [x] **Deepen generated-program loop termination analysis**
  (Owner: Tooling/Program Generator)
  - Scope: execute the first follow-up criterion in
    `docs/tiny_program_daemon.md` by replacing line-local infinite-loop checks
    with analysis of complete structured cyclic control-flow regions.
  - Result: validation now extracts balanced `while` bodies, recognizes
    literal infinite conditions independent of whitespace, and requires a
    provable update of the comparison's induction variable inside the loop.
  - Verification: focused regressions cover progress through a nested block,
    a loop that updates only unrelated state, and a spaced literal condition.

- [x] **Attach the TinyCPU instruction wire to the actual ROM data terminal**
  (Owner: TinyCPU/Hardware)
  - Cause: two earlier structural fixes mistook the ROM's upper-left XML anchor
    first for its data output and then offset only the horizontal coordinate.
    Both `(510,400)` and `(550,400)` miss the terminals centred vertically at
    `y=410`, which explains why only the autonomous clock changed in the table.
  - Result: the 22-bit instruction route now starts at the east-edge data output
    `(550,410)` and remains isolated from the west-edge address input
    `(510,410)` before reaching `OPCODE`.
  - Verification: the regression derives both terminals from the 40-by-20 ROM
    geometry, requires the complete data route, keeps the address net isolated,
    and rejects both previously used non-terminal endpoints.

- [x] **Attach the TinyCPU PC address slice to the ROM address terminal**
  (Owner: TinyCPU/Hardware)
  - Cause: the 16-to-12-bit PC splitter used the default symbol appearance while
    its checked-in wire started at the terminal position of the right-facing
    appearance. The apparent route therefore began beside, rather than on, the
    splitter output and left the ROM address input electrically undriven.
  - Result: the splitter now has the explicit, named `PC_ADDRESS` right-facing
    appearance that matches its 12-bit branch wire to the ROM.
  - Verification: a regression freezes the splitter orientation, all bit-lane
    assignments, and the complete branch route to the ROM address terminal.

- [x] **Apply taken TinyCPU jumps to the next program address**
  (Owner: TinyCPU/Hardware)
  - Cause: `JUMP_NOT_ZERO` was observable as a control output but did not select
    the encoded instruction operand for the `PC` input; the counter could only
    execute sequentially once its increment was repaired.
  - Result: a named 16-bit `NEXT_PC` multiplexer selects either `PC + 1` or the
    low 16-bit ROM operand, controlled by the existing `JNZ_TAKEN` result.
  - Verification: a focused connectivity regression follows both data inputs,
    the select input, and the multiplexer output through to the PC data pin.

- [x] **Increment the enabled TinyCPU program counter**
  (Owner: TinyCPU/Hardware)
  - Cause: enabling `FetchDecode.PC` did not make it advance because the second
    input of its next-address adder was still the default 16-bit zero. Every
    clock edge therefore reloaded `PC + 0`, repeatedly selecting ROM address
    zero even after the ROM-to-decoder route was repaired.
  - Result: the adder now receives an explicit 16-bit `1`, so ordinary clock
    edges compute the next sequential program address.
  - Verification: the focused PC regression now freezes both independent
    requirements: asserted register enable and an asserted, 16-bit increment
    constant connected to the adder input.

- [x] **Connect the TinyCPU instruction ROM to the decoder output**
  (Owner: TinyCPU/Hardware)
  - Cause: the program counter's address reached the ROM,
    but the ROM's 22-bit data terminal still ended without a wire. The top-level
    `OPCODE` output and all decode controls therefore remained undefined, so no
    fixture could reach its electrical halt condition.
  - Result: a dedicated 22-bit route now connects `FetchDecode.INSTRUCTION_ROM`
    directly to the `OPCODE` output without joining the nearby clock, reset,
    program-counter, or jump-control nets.
  - Verification: a focused electrical-connectivity regression resolves the
    complete ROM-to-output net instead of checking only XML coordinates.

- [x] **Enable the TinyCPU program counter in the electrical circuit**
  (Owner: TinyCPU/Hardware)
  - Cause: the `FetchDecode.PC` enable input was tied to the default zero-valued
    constant. Resetting the harness therefore changed the initial PC state but
    could not advance execution beyond ROM address zero, which explains why the
    follow-up evidence still contained hundreds of thousands of idle rows.
  - Result: the maintained circuit now drives the PC enable input high, allowing
    every rising edge to fetch the next instruction until the fixture reaches
    its normal or error halt condition.
  - Verification: a focused electrical-topology regression freezes both the
    asserted constant and its direct route to the register enable terminal.

- [x] **Drive the electrical TinyCPU fixtures through startup reset**
  (Owner: TinyCPU/Hardware)
  - Cause: the temporary Logisim harness replaced `RESET` with a constant zero,
    so a simulator start did not exercise the documented reset boundary. This
    was a real defect, but resetting alone could not overcome the separately
    disabled program-counter enable input.
  - Result: every AP-5/AP-11/AP-12 simulator harness now uses Logisim's
    `PowerOnReset` component, giving each independent process the synchronous
    startup assertion required by the maintained circuit.
  - Verification: focused harness coverage rejects a return to the inactive
    constant and still freezes the autonomous clock and retained raw table.

- [x] **Bind retained TinyCPU evidence to the AP-12 acceptance claims**
  (Owner: TinyCPU/Hardware)
  - Scope: close the gap between authentic inventory bytes and the report's
    claim that those bytes represent the complete mandatory release gate.
  - Result: offline verification now requires the pinned runtime versions, both
    named reset/restart raw and normalized traces, matching reproducibility
    metadata, and a positive matrix fixture count equal to its inventoried TSVs.
  - Verification: focused coverage rejects a substituted simulator version, a
    missing restart run, and a matrix count inconsistent with retained tables.

- [x] **Validate the retained TinyCPU evidence manifest before traversal**
  (Owner: TinyCPU/Hardware)
  - Scope: make malformed or hand-edited AP-12 reports fail predictably while
    preserving dependency-free offline verification.
  - Result: the verifier requires a JSON-object report and validates every
    inventory entry's canonical POSIX path, non-negative integer byte size, and
    lowercase SHA-256 value before comparing the directory or reading evidence.
  - Verification: focused coverage exercises a non-object report, a normalized
    path alias, a boolean size, and a malformed digest.

- [x] **Reject indirect files in retained TinyCPU acceptance evidence**
  (Owner: TinyCPU/Hardware)
  - Scope: harden the offline AP-12 verifier at the next trust boundary without
    changing the electrical acceptance matrix or requiring simulator access.
  - Result: bundle traversal uses filesystem metadata without following links
    and rejects symbolic links and non-regular evidence before reading bytes,
    so an inventory cannot attest to content outside the retained directory.
  - Verification: focused coverage replaces a valid evidence file with a link
    to byte-identical external content and confirms that verification fails.

- [x] **Make retained TinyCPU acceptance evidence independently verifiable**
  (Owner: TinyCPU/Hardware)
  - Scope: provide the bounded follow-up to the sealed AP-12 bundle without
    rerunning Logisim or changing the electrical acceptance matrix.
  - Result: the launcher can verify a retained schema-version-2 bundle offline,
    requiring an exact, sorted inventory and matching byte sizes and SHA-256
    digests. Missing, additional, reordered, or modified evidence is rejected.
  - Verification: focused tests cover an intact bundle, tampered evidence, and
    the dependency-free CLI path that deliberately skips Java and Logisim.

- [x] **Seal the TinyCPU release-acceptance evidence bundle**
  (Owner: TinyCPU/Hardware)
  - Scope: turn the next-cycle evidence-integrity candidate into a bounded
    post-AP-12 maintenance package without changing the accepted electrical
    test matrix.
  - Result: a passed schema-version-2 acceptance report inventories every raw
    table, normalized trace, and matrix artifact with its relative path, byte
    size, and SHA-256 digest. The report excludes itself and retains the
    schema-version-1 `started` marker, so incomplete runs remain distinguishable
    from complete, self-checking evidence bundles.
  - Verification: focused runner coverage recomputes every recorded digest and
    freezes deterministic POSIX-path ordering for portable artifact review.

- [x] **Complete the mandatory TinyCPU hardware release acceptance**
  (Owner: TinyCPU/Hardware)
  - Result: the AP-12 command performs two independent electrical reset-start
    runs, requires identical normalized 17-edge traces, and executes the full
    AP-11 ISA/error matrix in the same mandatory CI gate.
  - Evidence: CI retains both raw tables, normalized traces, every matrix table,
    and a versioned JSON report identifying the pinned simulator and Java.

- [x] **Execute the complete TinyCPU electrical ISA matrix**
  (Owner: TinyCPU/Hardware)
  - Completed slice: `tinycpu-electrical-matrix-v1.json` now freezes every
    version-1 opcode, its electrical test family, and one fixture identifier for
    each of the six sticky errors. The pinned launcher rejects missing, duplicate,
    extra, or renumbered coverage before starting Logisim.
  - Result: the launcher now replaces the program ROM in a temporary circuit for
    every declared opcode-family and sticky-error fixture, retains a raw table per
    fixture, and compares every electrical edge with the VM oracle.


- [x] **Export and accept the electrical AP-5 core trace**
  (Owner: TinyCPU/Hardware)
  - Success: clock the frozen AP-5 ROM in Logisim-evolution and compare the
    unmodified 16-pin table with the integration-boundary VM contract.
  - Result: the launcher drives a temporary copy of `TinyCPUMain` directly with
    an autonomous clock and inactive reset, avoiding unstable generated wrapper
    ports. It samples stable low phases, stops via tty `table,halt`, and retains
    the raw change-driven simulator output even when comparison fails.
  - Follow-up: AP 11 must replace the single embedded core ROM with small
    positive and error fixtures covering every opcode and sticky-error bit.

- [x] **Run the maintained TinyCPU circuit in a pinned headless Logisim environment**
  (Owner: TinyCPU/Hardware)
  - Scope: add a reproducible Logisim-evolution installation/launch path for
    local development and CI, pinning the simulator version and Java runtime
    instead of relying on an unversioned workstation installation.
  - Acceptance: a fresh CI checkout opens `hardware/logisim/TinyCPU.circ` in
    headless mode, fails on load or circuit errors, and records the exact
    simulator version in the job log.
  - Boundary: this package establishes the real simulator as a test dependency
    and proves that the project loads. It does not claim VM/CPU parity until a
    following package captures electrical pin observations.
  - Roadmap: this is AP 9 in `docs/tiny_cpu_roadmap.md`; AP 10 then exports the
    AP-5 core trace, before the full ISA matrix is attempted.
  - Result: CI installs Temurin 21.0.8+9.0.LTS and the maintained launcher fetches
    Logisim-evolution 4.1.0 from its versioned release URL, logs both versions,
    and loads `TinyCPUMain` through the non-interactive table interface. Unit
    tests freeze the runtime check, download URL, and exact load command.
  - Follow-up: AP 10 must capture the AP-5 integration pins from this real
    simulator and submit the raw table to the existing comparator.

## Open-task audit (2026-08-19)

- [x] **Re-validate the documented backlog before opening another work package**
  (Owner: Project Lead)
  - Audit: searched every tracked Markdown file for unchecked checklist entries
    (`- [ ]`), including the root task list, active plans, and roadmaps.
  - Result: no unchecked documented work package remained at the time of the
    audit. The new AP-9-to-AP-12 electrical-simulation sequence supersedes that
    state without re-opening accepted structural integration packages.

## Next documented work package (completed 2026-08-19)

- [x] **Accept the Logisim integration pin table without manual JSON rewriting**
  (Owner: TinyCPU/Hardware)
  - Success: consume the table logger's flat CSV/TSV rows while preserving the
    existing edge-by-edge integration-boundary comparison contract.
  - Result: `tiny_cpu_trace.py --integration --check-logisim-table` maps the
    sixteen named output, sticky-error, and halt columns into the versioned
    trace schema. It rejects missing columns, undefined electrical bits, and
    row counts that differ from the matching assembly execution.
  - Follow-up: install Logisim-evolution in CI and feed this adapter with a
    table captured from the maintained circuit; the adapter and VM expectation
    still do not constitute electrical-simulation evidence by themselves.

## Next documented work package (completed 2026-08-19)

- [x] **Remove the abandoned TinyCPUMain wire tail**
  (Owner: TinyCPU/Hardware)
  - Wiring audit: the L-shaped route from `(210,250)` via `(960,250)` to
    `(960,590)` ended without a consumer and carried no integration signal.
  - Result: both dead segments are removed without changing the adjacent clock,
    reset, decode, or data nets. A focused topology regression prevents the
    visually misleading route from being reintroduced.
  - Follow-up: export the already documented integration-boundary scenarios
    directly from Logisim-evolution when the simulator becomes available in CI.

## Next documented work package (completed 2026-08-19)

- [x] **Add the TinyCPUMain end-to-end boundary trace**
  (Owner: TinyCPU/Hardware)
  - Wiring audit: the dependency-free inspector and topology regressions confirm
    that every `TinyCPUMain` port is connected, with no routing or width
    conflicts; the two reported reserved-lane overlaps are placement warnings,
    not electrical shorts.
  - Success: freeze edge-by-edge observations for normal halt, explicit error
    halt, and an invalid `PRINT`, including all distinct print and halt event
    pins plus sticky errors and post-edge halt state.
  - Result: `tinycpu_integration_trace.json` supplies the three reference
    scenarios, the trace helper models the pre-edge Logisim output-pin sampling
    boundary, and the fresh-checkout verifier rejects drift in any observation.
  - Follow-up: when Logisim-evolution is available in CI, export these same pin
    observations directly from the simulator and compare them to the frozen
    fixture; do not describe the dependency-free reference replay as an
    electrical simulation.

## Next documented work package (completed 2026-08-19)

- [x] **Close the TinyCPU top-level integration acceptance audit**
  (Owner: TinyCPU/Hardware)
  - Success: reconcile the maintained circuit with the remaining integration
    checklist and document one unambiguous next boundary after all result,
    sticky-error, print, and halt routes have been accepted.
  - Result: the checklist now records the already integrated operation result
    tree and its independent `OVERFLOW`, `DIVIDE_BY_ZERO`, and
    `INVALID_OPERAND` sticky-error routes. The top-level plan also reflects the
    completed accumulator, status, and distinct halt-output wiring instead of
    advertising superseded follow-ups.
  - Follow-up: exercise the completed electrical boundary in an end-to-end
    Logisim trace that includes normal halt, error halt, and invalid output
    validity rather than adding another structural route.

## Next documented work package (completed 2026-08-19)

- [x] **Integrate the TinyCPU HALT output paths**
  (Owner: TinyCPU/Hardware)
  - Success: export `HALT` and `HALT_ERROR` as electrically distinct observable
    outcomes so a consumer can retain the stopped state without losing the
    reason execution ended.
  - Result: `HALT_ENABLE` carries only the normal halt control, while
    `HALT_ERROR_ENABLE` carries only the explicit error-halt control. A topology
    regression freezes both routes and proves that the event nets never join.


## Next documented work package (completed 2026-08-18)

- [x] **Integrate the TinyCPU PRINT output paths**
  (Owner: TinyCPU/Hardware)
  - Success: export `PRINT` and `PRINT_ADDRESS` as electrically separate output
    events, each accompanied by the value source and validity bit required to
    decide whether the event may be consumed.
  - Wiring audit: restored the three isolated `STORE_*` request routes after
    the latest manual gate move had joined two inputs and left the offset mode
    disconnected. The repaired routes retain the established memory-write
    behavior while the output channels are added independently.
  - Result: `PRINT` exposes the accumulator value and accumulator validity,
    while `PRINT_ADDRESS` exposes the selected memory value and memory-cell
    validity. Distinct enable, value, and validity nets prevent either output
    mode from masquerading as the other. A topology regression freezes both
    three-signal channel contracts.
  - Follow-up: integrate the `HALT` and `HALT_ERROR` controls with distinct
    observable halt outcomes.


## Next documented work package (completed 2026-08-18)

- [x] **Integrate the TinyCPU accumulator-based NOT path**
  (Owner: TinyCPU/Hardware)
  - Wiring audit: the `NOT` control already reaches the isolated unary box,
    and the shared operation result and validity buses already reach the
    accumulator data inputs without conflicting drivers.
  - Result: the combined accumulator-write request now also reaches
    `Datapath.ACC_LOAD`, so an active `NOT` commits the inverted accumulator
    value and propagates its validity on the clock edge. A topology regression
    protects the complete control, data, validity, and write-enable path.
  - Follow-up: integrate the two output controls, `PRINT` and
    `PRINT_ADDRESS`, as a separate package.

## Next documented work package (completed 2026-08-18)

- [x] **Integrate the TinyCPU STORE memory-write paths**
  (Owner: TinyCPU/Hardware)
  - Success: combine the three writable `STORE_*` addressing modes into the
    sole memory write-enable request while retaining the shared effective-
    address selection used by loads and binary operations.
  - Result: `STORE_ADDRESS`, `STORE_ADDRESS_REGISTER`, and
    `STORE_ADDRESS_REGISTER_PLUS_OFFSET` reach distinct inputs on the named
    write-request gate. Its output exclusively enables memory writes, and the
    accumulator value plus its validity bit form the stored payload.
  - Follow-up: integrate the accumulator-based `NOT` path before adding the
    two output controls, `PRINT` and `PRINT_ADDRESS`.

## Next documented work package (completed 2026-08-17)

- [x] **Audit the TinyCPU non-binary data paths**
  (Owner: TinyCPU/Hardware)
  - Wiring audit: the latest `TinyCPUMain` redraw had connected
    `STORE_ADDRESS_REGISTER` to the `AND_ADDRESS_REGISTER` operation input and
    `OR_ADDRESS_REGISTER_PLUS_OFFSET` to the corresponding AND input. The
    STORE and OR routes remain intact, while both AND controls once again use
    their own electrically isolated routes.
  - Result: the existing `LOAD_*` source-selection and validity stages and the
    accumulator-based `NOT` path remain correctly wired. The audit also
    confirms that the memory write-enable/data inputs and the two print
    controls are not integrated yet; they must not be mistaken for completed
    paths merely because address selection is already present.
  - Follow-up: integrate the three `STORE_*` modes so that only their combined
    request enables memory writes, with accumulator value and validity as the
    stored payload.

## Next documented work package (completed 2026-08-17)

- [x] **Integrate the TinyCPU XOR result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Wiring audit: repaired two regressions in the manually redrawn
    `TinyCPUMain`: `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` again reaches the
    matching effective-address input, and the accidentally joined
    `OR_ADR_REG`/sticky-error routes are electrically separate again.
  - Success: connect all four `XOR_*` addressing modes to the extracted box
    and merge its neutral result, validity, and activity into the maintained
    operation boundary without assigning arithmetic-overflow semantics.
  - Result: the version-1 opcode table appends the four XOR modes, the decoder
    exports their controls, and `Operations` uses explicit second-stage OR
    gates so the compact seven-way merge and its established routing remain
    undisturbed. Structural tests freeze the repaired top-level routes and the
    complete XOR path through the VM, decoder, boundary, and FBox.
  - Follow-up: audit the remaining non-binary `STORE_*`, `NOT`, `PRINT`,
    `PRINT_ADDRESS`, and `LOAD_*` data paths before further result-tree work.

## Next documented work package (completed 2026-08-17)

- [x] **Extract the TinyCPU XOR result-and-validity FBox**
  (Owner: TinyCPU/Hardware)
  - Review: the compacted `Operations` redraw is electrically complete: it has
    no unconnected ports, routing conflicts, or width conflicts. Its single
    remaining local tunnel, three-input overflow merge, and relocated result
    lane are now reflected by topology-based structural checks.
  - Success: give all four `XOR_*` addressing modes the established explicit
    accumulator/immediate-or-memory operand and validity boundary without
    arithmetic overflow semantics.
  - Result: the tunnel-free `XorSubCircuit` selects operand data and validity
    in parallel and delegates the neutral-gated operation to the leaf
    `XorArithmeticCircuit`. The circuit inspector now understands XOR-gate
    terminals, and generated diagnostics plus structural coverage freeze the
    new contract.
  - Follow-up: integrate the XOR box behind `Operations` and merge its result,
    validity, and invalid-operand activity without disturbing the manual layout.

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

## TinyCPU external-trace acceptance update (2026-08-19)

- [x] **Make exported integration-boundary traces directly comparable**
  (Owner: TinyCPU)
  - Result: `tiny_cpu_trace.py --integration --check` now derives the expected
    print/halt boundary observations from a matching assembly program and
    compares them edge-by-edge with an exported JSON trace.
  - Verification: CLI regressions cover a matching three-edge boundary trace
    and reject full-state memory watches in integration mode.
  - Follow-up: capture the observed JSON directly from Logisim-evolution once
    the simulator is installed in CI; the VM-derived expectation remains a
    comparator and is not electrical-simulation evidence.

## Program-generator validation update (2026-08-22)

- [x] **Require provably non-zero division operands** (Owner: Tooling/Program Generator)
  - Scope: execute the next follow-up criterion in
    `docs/tiny_program_daemon.md` after structured loop termination analysis.
  - Result: generated programs now accept division only when conservative local
    evidence proves the divisor non-zero; literal zero, unknown parameters, and
    reassignment after a returning zero guard are rejected.
  - Verification: focused regressions cover a returning zero guard, an
    unguarded parameter, and invalidation of guard evidence by reassignment.

## Program-generator resource-bounds update (2026-08-22)

- [x] **Bound generated heap allocations and loop iterations** (Owner: Tooling/Program Generator)
  - Scope: execute the next follow-up criterion in
    `docs/tiny_program_daemon.md` after non-zero divisor analysis.
  - Result: generated programs require fixed heap sizes of at most 4096 slots
    and statically provable comparison-loop bounds of at most 10,000 iterations.
    The logistic-map template now exposes its existing eight-step limit directly
    in the loop condition so it satisfies the same conservative gate.
  - Verification: focused regressions cover accepted bounded resources, dynamic
    heap sizes, excessive iteration counts, and parameter-dependent loop bounds.

## Program-generator determinism update (2026-08-22)

- [x] **Add an optional deterministic generation profile** (Owner: Tooling/Program Generator)
  - Scope: execute the next follow-up criterion in
    `docs/tiny_program_daemon.md` after resource-bound validation.
  - Result: `--deterministic` rejects generated programs that call supported
    time or random sources, while the default profile remains backward
    compatible and documentation text cannot trigger false positives.
  - Verification: focused regressions cover time and random calls, the opt-in
    default, comment/string handling, and CLI activation.

## Program-generator readability update (2026-08-22)

- [x] **Enforce generated-program style and readability rules**
  (Owner: Tooling/Program Generator)
  - Scope: execute the final follow-up criterion in
    `docs/tiny_program_daemon.md` after the deterministic generation profile.
  - Result: generated programs require an explanatory comment and `snake_case`
    declarations, with category-specific limits of 80 or 100 source lines.
  - Verification: focused regressions cover missing comments, invalid function
    and variable names, category limits, and all curated default templates.

## Program-source quarantine update (2026-08-22)

- [x] **Acquire allowlisted external sources into quarantine**
  (Owner: Tooling/Program Generator)
  - Scope: execute the first documented pipeline package after completing the
    local generator quality criteria; acquisition must never execute or parse
    downloaded content.
  - Result: a dedicated CLI accepts HTTPS sources only from RosettaCode and raw
    GitHub, enforces a 256 KiB default limit, revalidates redirect targets, and
    atomically stores non-executable bytes with provenance and a SHA-256 digest.
  - Verification: focused regressions cover byte-exact retention, metadata and
    permissions, rejected schemes/hosts/credentials/ports/redirects, and the
    size boundary. Security scanning remains the next pipeline package.

## Program-source security-scan update (2026-08-22)

- [x] **Statically scan quarantined external sources**
  (Owner: Tooling/Program Generator)
  - Scope: execute the second documented import-pipeline package without
    parsing, importing, or executing untrusted content.
  - Result: the scanner verifies the immutable payload against its provenance,
    permits only UTF-8 `.py` and `.tiny` sources, rejects binary and dangerous
    static signatures, and writes an atomic versioned verdict. Only a passing
    report names automatic porting as an allowed next stage.
  - Verification: focused regressions cover a passing report, content-type and
    signature rejections, tampered provenance, symlinks, and report permissions.
    Automatic TinyLanguage porting remains the next pipeline package.

## Program-source sandbox update (2026-08-23)

- [x] **Run and assess approved ports under resource limits**
  (Owner: Tooling/Program Generator)
  - Scope: execute the next documented import-pipeline package after automatic
    porting without trusting a stale or substituted output artifact.
  - Result: the sandbox stage revalidates the port report and output hash, runs
    TinyLanguage in an isolated child process with an empty working directory,
    timeout and OS resource ceilings, and records a versioned pass/fail report.
  - Verification: focused regressions cover a successful program, a runtime
    failure that is not promoted, and byte tampering after port approval.
    Optional GUI-wrapper generation remains the next pipeline package.

## Program-source GUI-wrapper update (2026-08-23)

- [x] **Generate an optional GUI for approved sandbox results**
  (Owner: Tooling/Program Generator)
  - Scope: complete the final documented import-pipeline package without
    allowing a desktop launcher to bypass the preceding sandbox boundary.
  - Result: the generator revalidates the exact source and captured-output
    hashes from a passing sandbox report, embeds that output in a read-only Tk
    presentation, and records source, output, and wrapper hashes in a versioned
    audit report.
  - Verification: focused regressions compile the generated launcher, confirm
    that it contains no subprocess execution path, and reject failed or
    subsequently tampered sandbox results. The documented pipeline is complete.

## TinyCPU schematic-regression update (2026-08-23)

- [x] **Preserve TinyCPU electrical contracts across schematic adjustments**
  (Owner: TinyCPU/Hardware)
  - Cause: the latest visual adjustment removed non-default constants and stable
    component attributes from `FetchDecode` and `Operations`, disconnected the
    accumulator store/print routes, and replaced the isolated JNZ status tunnel
    with a route through occupied top-level wiring.
  - Result: restored the last electrically verified schematic, including the
    enabled and incrementing program counter, named selectors and range check,
    accumulator-backed store/print channels, and the single documented JNZ
    tunnel pair.
  - Verification: the focused circuit, Logisim-topology, and launcher suites
    again freeze the complete electrical contract; future visual edits must
    preserve these attributes and nets rather than treating them as cosmetic.

## TinyCPU roadmap-consistency update (2026-08-23)

- [x] **Retire the stale AP-9 next-package marker** (Owner: TinyCPU/Planning)
  - Scope: reconcile the expansion roadmap with the completed AP-9-to-AP-12
    status and the retained, independently verifiable release evidence.
  - Result: the expansion roadmap now describes electrical acceptance as a
    completed boundary, preserves the maintenance and evidence rules, and does
    not advertise an already accepted package as the next implementation task.
  - Verification: a documentation regression compares the AP completion
    checklist with the expansion-roadmap status and requires future TinyCPU
    work to be explicitly scoped rather than inferred from stale prose.

## TinyCPU self-test documentation update (2026-08-23)

- [x] **Document a beginner-friendly TinyCPU.circ self-test**
  (Owner: TinyCPU/Documentation)
  - Scope: triage and complete the first bounded package after the intentionally
    closed backlog by turning the existing AP-12 operator details into a short,
    standalone German procedure.
  - Result: the guide covers prerequisites, the one-command electrical gate,
    an existing-JAR fallback, offline evidence verification, visual inspection,
    and common failures; the main documentation links to it directly.
  - Verification: documentation checks freeze the executable command names,
    maintained circuit path, and expected passed-report location.

## TinyCPU electrical-contract recovery update (2026-08-23)

- [x] **Recover the verified TinyCPU circuit after a visual adjustment**
  (Owner: TinyCPU/Hardware)
  - Scope: triage and complete the next bounded package after the closed
    backlog by checking the latest schematic-only change against the existing
    electrical contract regressions.
  - Cause: the adjustment removed non-default component values and stable
    labels from `FetchDecode` and `Operations`. This disabled PC advancement
    and made the range, next-PC, and accumulator-result selectors
    unidentifiable; it also made the checked-in diagnostic leaves stale.
  - Result: restored the last regression-verified circuit definition, including
    the asserted PC enable and increment, the named address/range/next-PC
    components, and the immediate-value result and validity selectors.
  - Verification: the focused circuit, topology, and addition-wiring suites
    pass again (117 passed, with 11 explicitly expected failures). Future
    schematic adjustments must preserve component attributes as part of the
    electrical design rather than treating them as visual metadata.

## TinyCPU historical-roadmap closure update (2026-08-23)

- [x] **Close stale follow-up language in the detailed hardware documentation**
  (Owner: TinyCPU/Documentation)
  - Scope: execute the next documented package by reconciling the historical
    staged-integration narrative with the already completed AP-12 boundary.
  - Result: the detailed roadmap marks the manual-overview reconciliation as
    completed, and both hardware documents describe DIV, non-binary data paths,
    accumulator selection, store, and print integration as completed work.
  - Verification: a roadmap-consistency regression rejects the obsolete
    future-tense markers and requires the completed follow-package heading.

## TinyCPU post-adjustment recovery update (2026-08-23)

- [x] **Restore TinyCPU electrical attributes after the latest schematic adjustment**
  (Owner: TinyCPU/Hardware)
  - Scope: execute the next bounded package by validating the latest circuit
    adjustment against the checked-in electrical-contract and diagnostic-leaf
    regressions.
  - Cause: the adjustment again removed the asserted program-counter constants
    and the stable `PC_ADDRESS`, `PC_RANGE`, `NEXT_PC`, and accumulator-selector
    labels. The edited leaf sheets therefore no longer matched their generated
    diagnostics, and the program counter and immediate-load boundary lost
    machine-significant configuration.
  - Result: restored the regression-verified circuit definition while leaving
    the documented AP-12 acceptance boundary unchanged.
  - Verification: the focused circuit, Logisim-topology, addition-wiring,
    roadmap, and self-test-guide suites pass with the expected simulator-only
    cases explicitly marked as expected failures.

## TinyCPU Fetch/Decode recovery update (2026-08-26)

- [x] **Recover Fetch/Decode after the latest schematic adjustment**
  (Owner: TinyCPU/Hardware)
  - Scope: execute the next bounded package by validating the adjusted
    `FetchDecode` sheet and its automatically derived top-level symbol against
    the checked-in electrical contract.
  - Cause: the adjustment moved the ROM and control path, removed the enabled
    program-counter constants and stable range/next-PC components, disconnected
    reset and the ROM address branch, and changed the generated symbol's pin
    positions without reconnecting the top-level clock and JNZ nets.
  - Result: restored the last electrically verified `FetchDecode` definition
    and its matching top-level connections without changing the completed
    AP-12 acceptance boundary.
  - Verification: the focused Logisim suite again passes all 77 executable
    checks; the 10 simulator-dependent cases remain explicitly expected
    failures.

## TinyCPU ALU-documentation reconciliation update (2026-08-26)

- [x] **Retire the obsolete TinyCPU ALU redesign follow-up**
  (Owner: TinyCPU/Documentation)
  - Scope: execute the next explicitly documented TinyCPU follow-up by checking
    the historical ALU sketch against the accepted machine and schematic.
  - Cause: the sketch still presented an unimplemented `ALU` sheet, 24-bit
    words, and 8-bit opcodes as the next step even though the accepted design
    uses `Operations`, 22-bit words, and 6-bit opcodes.
  - Result: the note now records the maintained operation boundaries and
    authoritative widths and explicitly closes the incompatible redesign.
  - Verification: a roadmap-consistency regression reads the versioned machine
    contract and prevents the stale next-step language from returning.

## TinyCPU FBox connection closure (2026-08-27)

- [x] **Close every visible FBox port before versioning the completed baseline**
  (Owner: TinyCPU/Hardware)
  - Scope: audit every input and output of every subcircuit instance rather
    than accepting an FBox as soon as any one of its ports is connected.
  - Cause: the former inspector checked the FBox as a whole. Consequently,
    compatibility inputs and unused status outputs could remain visibly open
    while the integration sheet was still reported as connected.
  - Result: all such inputs now have explicit named inactive drivers and all
    intentionally unused outputs have named monitor probes, both on
    `TinyCPUMain` and inside `DecodeSignals`.
  - Verification: the inspector reports every maintained sheet connected, and
    a focused regression rejects an otherwise connected FBox with one open
    port.
