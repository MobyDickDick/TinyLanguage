# Interval arithmetic contract and acceptance

Work package 8, adoption date: 2026-11-05. This contract covers
`src_tiny/number_intervall.tiny` on the Python reference interpreter. It does not
add intervals to the frozen 1.0 stability target or qualify compiler backends.

## Represented sets

`NumberIntervall` represents a closed subset of the **real** numbers. Infinity
is an endpoint sentinel, not a member. The historical field name `error` now
distinguishes valid shapes as well as error states. Canonical bounds are binary64.

| `error` | Meaning of `lower = l`, `upper = u` |
| --- | --- |
| `normal` | `[l,u]`, finite `l <= u`; equality is a singleton. |
| `wrapped_interval` | `(-infinity,u] union [l,infinity)`, `l > u`. The gap `(u,l)` is excluded. |
| `upper_bound_is_plus_infinity` | `[l,infinity)`, `upper = +infinity`. |
| `lower_bound_is_minus_infinity` | `(-infinity,u]`, `lower = -infinity`. |
| `any_number` | The entire real line, bounds `(-infinity,+infinity)`. |
| `empty_interval` | The empty set; placeholder bounds `(0,0)` have no meaning. |
| `invalid_number` | Invalid input, unknown status, or an approximation used in guaranteed arithmetic. No represented set. |
| `approximate` | An unqualified `Math` estimate. No enclosure guarantee. |

`NumberIntervall(l,u)` constructs an ordinary interval if `l <= u`, and an
exterior interval if `l > u`. It never swaps reversed bounds. NaN, booleans and
non-numeric bounds are invalid. Infinite singletons contain no real elements
and become empty; `[+infinity,-infinity]` is also empty. Semi-infinite and whole
line inputs are canonicalized. Private legacy constructors obey the same rules.
Legacy `wrapped_interval` tags with overlapping rays become the entire line.
Legacy scalar `plus_infinity` and `minus_infinity` states carry no known finite
magnitude, so conversion conservatively yields the entire line, not `{infinity}`.

## Guaranteed operations and rounding

The supported arithmetic operations are `+`, `-`, `*`, `/`. Their result
encloses all pointwise real results over the represented operand sets. Division
excludes denominator values equal to zero. Division by `[0,0]` therefore returns
empty, including `[0,0]/[0,0]`. An invalid operand takes precedence; otherwise an
empty operand produces empty. `any_number` is a set, not an absorbing error:
for example, `{0} * any_number = {0}`.

The implementation decomposes exterior sets into rays, computes component
arithmetic with exact rational finite bounds, takes closure, and merges overlaps.
Two exterior rays retain their gap. Other disconnected finite unions use their
convex hull, which can lose precision while preserving enclosure. Taking closure
may include unattained limits, for example zero in `1/[1,infinity)`.

Final lower endpoints round towards negative infinity and upper endpoints
towards positive infinity. For an exterior interval this shrinks the excluded
gap. Exactly representable results stay exact. Overflow becomes an unbounded
enclosure: a positive value above the largest finite float has lower bound
`float_max` and upper bound `+infinity`; the negative case is symmetric.
Underflow rounds outwards through zero and subnormal values. Signed zeros both
mean the real number zero. No global floating-point rounding mode is changed.

`src/tiny_intervals.py` provides a small host kernel independent of runtime
objects. Native stdlib adapters expose its constructor, neighbor and arithmetic
primitives to the Tiny class. The wheel's module discovery and frozen runtime's
source/hidden-import discovery include this module. The Tiny class is not a
standalone self-hosted implementation of exact rational arithmetic. This is a
correctness-first implementation; exact rational intermediates cost more than
ordinary float arithmetic and no performance bound is promised.

## Inputs, conversion and display

The guarantee starts with **stored numeric values**. A binary float is treated
as its exact rational value; a decimal literal already rounded by parsing does
not recover its intended decimal value. Integer constructor inputs are retained
exactly during conversion and rounded outwards if binary64 cannot hold them.
Promotion of plain numbers and `Number` objects follows this same rule.
`Number.error == "rounded"` encloses the stored value only: its earlier rounding
history supplies no error bound. Its lost real value cannot be reconstructed.
Unknown `Number` states become invalid; scalar infinity/unknown-number states
and stored infinite scalar values convert to the entire line conservatively.
Scalar NaN becomes invalid. This promotion differs from constructor bounds:
an overflowed scalar has lost finite magnitude information, whereas an infinite
endpoint is a boundary sentinel. `Number` arithmetic itself is unchanged.

`interval_number(v)` intentionally adds the immediate binary64 neighbor on
each side of the directed conversion of `v`. Directions are actual infinities,
not `v +/- 1`, which can equal `v` at large magnitudes. At finite float extremes,
the envelope can be semi-infinite. Nonfinite infinity input is conservative
`any_number`; NaN is invalid.

Inspect `lower`, `upper` **and** `error` for authoritative bounds. Ordinary
center/radius printing is a rounded display estimate, not an interchangeable
enclosure representation. Exterior and unbounded sets print their endpoints;
subnormal ranges and overflowing radii also print bounds. Approximate estimates
print with `(approximate)`; invalid/empty states print their names.

## Explicit exclusions

The legacy `Math` interval overloads (`abs`, `min`, `max`, `pow`, `sqrt`, `round`,
`floor`, `ceil`, `clamp`) are estimates without an established enclosure
contract. Their interval estimates now have `error == "approximate"`, even when
a particular numeric result happens to be exact. Whole-line, invalid and empty
fallback states retain their names. Feeding an approximate result into the four
guaranteed operators returns `invalid_number`; do not relabel it as `normal`.
`Math.sign` is a sign/uncertainty query returning a scalar or `Number`, not an
interval enclosure operation. Scalar `Math` behavior is unchanged.

Interval exponentiation via `^`, remainder, transcendental functions, comparisons
and standalone Tiny/native/C/LLVM execution have no interval enclosure promise.
Mutable public fields can also invalidate a previously constructed object;
arithmetic validates the supplied bounds/status again rather than trusting them.

## Migration and executable examples

Load `src_tiny/number_intervall.tiny` and append the following example (the test
suite concatenates the files in memory and executes this exact Markdown block):

```tiny
def quotient = NumberIntervall(-2, 3) / NumberIntervall(-5, 0.5);
print(quotient.error);
def sum = NumberIntervall(1, 1) + NumberIntervall(2 ^ -53, 2 ^ -53);
print(sum.lower);
print(sum.upper);
print(sum.error);
```

Expected lines: `any_number`, `1.0`, `1.0000000000000002`, `normal`.
For every real quotient `q`, choose a nonzero denominator `y` sufficiently close
to zero that `q*y` lies in `[-2,3]`; then `x=q*y` is an allowed numerator.
Consequently the old `[6,-4]` result excluded valid values such as zero.
For the addition, the exact rational result is `1 + 1/9007199254740992`, strictly
between adjacent binary64 floats `1` and `1.0000000000000002`. The old `[1,1]`
was too narrow. These derivations define the expected results independently.

Other observable corrections: `[2,3]/[-1,1]` is exterior `[2,-2]`, not `[3,-3]`;
negative numerators divided by `[0,1]` produce a negative ray; zero-only divisors
are empty; reciprocals of exterior intervals can be ordinary intervals. Exact
endpoint checks may need to become enclosure checks. Update status checks and
serialized fields for true infinite bounds. Removed private float-expansion and
overflow helpers are replaced by the native primitives. Applications relying
on `Math` interval estimates must handle `approximate` explicitly.

## Acceptance evidence

`tests/detailtests/test_interval_enclosure.py` checks direct exact rational
endpoint extrema and their tight binary64 bounds for all four operators,
deterministic random finite float patterns, overflow, cancellation, signed zero,
subnormals, integer conversion, neighbor directions and invalid states. A
separate pointwise rational oracle covers all pairings of ordinary, exterior,
unbounded, whole-line and empty sets. It does not call implementation decode,
reciprocal, merge or rounding helpers. Integration tests exercise actual Tiny
fields, both copy-on-call modes, mixed `Number`/scalar promotion, the Markdown
example and explicitly approximate Math results. Existing formatting expectations
were corrected using the set derivations above, not preserved as oracles.

Retained commands, source identity and results are recorded in
[`artifacts/interval-arithmetic/checkpoint.json`](../artifacts/interval-arithmetic/checkpoint.json).
This acceptance concerns the reference interpreter and work package 8; platform,
release and the wider independent-backend audit remain separate work packages.
