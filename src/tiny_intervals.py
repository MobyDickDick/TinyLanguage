"""Set-based interval arithmetic for the reference interpreter.

Compute finite bounds as exact rationals, then round final bounds outwards to
binary64. Infinity is a boundary sentinel, never an element of the real set.
This module has no dependency on the runtime or Tiny object layout.
See docs/interval_arithmetic_contract.md for the contract and exclusions.
"""

from __future__ import annotations

import math
import sys
from fractions import Fraction
from typing import Mapping

Bound = Fraction | float
Component = tuple[Bound, Bound]
Interval = tuple[float, float, str]
NEG_INF = -math.inf
POS_INF = math.inf
INVALID: Interval = (0.0, 0.0, "invalid_number")
EMPTY: Interval = (0.0, 0.0, "empty_interval")
ENTIRE: Interval = (NEG_INF, POS_INF, "any_number")


def _exact(value: int | float) -> Bound:
    """Reject NaNs/non-numbers; preserve integers and binary floats exactly."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("interval bounds must be numbers")
    if isinstance(value, float):
        if math.isnan(value):
            raise ValueError("NaN is not an interval bound")
        if math.isinf(value):
            return value
    return Fraction(value)


def _directed(value: Bound, upward: bool) -> float:
    """Tight directed binary64 conversion, including overflow and underflow."""
    if value == NEG_INF or value == POS_INF:
        return float(value)
    try:
        rounded = float(value)
    except OverflowError:
        rounded = POS_INF if value > 0 else NEG_INF
    if math.isinf(rounded):
        if rounded > 0:
            return POS_INF if upward else sys.float_info.max
        return -sys.float_info.max if upward else NEG_INF
    exact_rounded = Fraction(rounded)
    if upward and exact_rounded < value:
        return math.nextafter(rounded, POS_INF)
    if not upward and exact_rounded > value:
        return math.nextafter(rounded, NEG_INF)
    return rounded


def _merge(parts: list[Component]) -> list[Component]:
    """Merge overlapping closed components, discarding infinite singletons."""
    merged: list[Component] = []
    for lo, hi in sorted(parts):
        if lo > hi or lo == POS_INF or hi == NEG_INF:
            continue
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def _encode(parts: list[Component]) -> Interval:
    """Preserve ordinary/exterior sets; use the hull for other finite unions."""
    parts = _merge(parts)
    if not parts:
        return EMPTY
    if len(parts) == 2 and parts[0][0] == NEG_INF and parts[1][1] == POS_INF:
        # For an exterior interval the gap must shrink under outward rounding.
        lower = _directed(parts[1][0], False)
        upper = _directed(parts[0][1], True)
        if lower > upper:
            return lower, upper, "wrapped_interval"
        return ENTIRE
    lo = _directed(parts[0][0], False)
    hi = _directed(parts[-1][1], True)
    if lo == NEG_INF and hi == POS_INF:
        return ENTIRE
    if hi == POS_INF:
        return lo, hi, "upper_bound_is_plus_infinity"
    if lo == NEG_INF:
        return lo, hi, "lower_bound_is_minus_infinity"
    return lo, hi, "normal"


def _decode(lower: int | float, upper: int | float, error: str) -> list[Component]:
    """Interpret canonical fields and historical status-tagged objects."""
    if error == "empty_interval":
        return []
    if error in {"any_number", "plus_infinity", "minus_infinity"}:
        # Scalar overflow states carry no finite magnitude information.
        return [(NEG_INF, POS_INF)]
    if error not in {"normal", "wrapped_interval", "upper_bound_is_plus_infinity",
                     "lower_bound_is_minus_infinity"}:
        raise ValueError("invalid or approximate interval")
    lo, hi = _exact(lower), _exact(upper)
    if error == "upper_bound_is_plus_infinity":
        hi = POS_INF
    if error == "lower_bound_is_minus_infinity":
        lo = NEG_INF
    if lo > hi:
        return _merge([(NEG_INF, hi), (lo, POS_INF)])
    if error == "wrapped_interval":
        # A historical wrapped object with no gap means the entire real line.
        return [(NEG_INF, POS_INF)]
    return _merge([(lo, hi)])


def bounds(lower: int | float, upper: int | float, error: str = "normal") -> Interval:
    """Canonicalize a constructor or a legacy status-tagged interval."""
    try:
        return _encode(_decode(lower, upper, error))
    except (ValueError, TypeError):
        return INVALID


def scalar(value: int | float, error: str = "normal") -> Interval:
    """Promote a stored scalar, treating overflow as unknown finite magnitude.

    Unlike constructor endpoints, scalar infinities describe a lost value,
    not an infinite boundary. Rounded Number history cannot be recovered.
    """
    if error in {"normal", "rounded"}:
        if isinstance(value, float) and math.isinf(value):
            return ENTIRE
        return bounds(value, value)
    return bounds(0, 0, error)


def neighboring(value: int | float) -> Interval:
    """Enclose a finite stored value and its adjacent binary64 bounds.

    Directions are true infinities: value +/- 1 can equal value at large
    magnitudes. Directed conversion also encloses nonrepresentable integers.
    """
    try:
        exact = _exact(value)
        if exact in (NEG_INF, POS_INF):
            return ENTIRE
        lo, hi = _directed(exact, False), _directed(exact, True)
        if math.isfinite(lo):
            lo = math.nextafter(lo, NEG_INF)
        if math.isfinite(hi):
            hi = math.nextafter(hi, POS_INF)
        return bounds(lo, hi)
    except (ValueError, TypeError):
        return INVALID


def _product(a: Bound, b: Bound) -> Bound:
    # 0 times an unbounded set is {0}; 0*infinity must not produce NaN.
    if a == 0 or b == 0:
        return Fraction(0)
    if a in (NEG_INF, POS_INF) or b in (NEG_INF, POS_INF):
        return POS_INF if (a > 0) == (b > 0) else NEG_INF
    return a * b


def _multiply(a: Component, b: Component) -> Component:
    """Extrema on a connected rectangle occur among its four corner products."""
    products = [_product(x, y) for x in a for y in b]
    return min(products), max(products)


def _reciprocal(part: Component) -> list[Component]:
    """Closure of {1/x: x in part, x != 0}, splitting at zero."""
    lo, hi = part
    result = []
    if lo < 0:
        result.append((NEG_INF if hi >= 0 else 1 / hi,
                       Fraction(0) if lo == NEG_INF else 1 / lo))
    if hi > 0:
        result.append((Fraction(0) if hi == POS_INF else 1 / hi,
                       POS_INF if lo <= 0 else 1 / lo))
    return result


def binary(op: str, left: Mapping, right: Mapping) -> Interval:
    """Enclose pointwise +, -, *, / over represented sets, excluding y=0.

    Invalid/approximate operands propagate invalid_number. An empty Cartesian
    product is empty, including division by the zero-only interval.
    """
    if op not in {"+", "-", "*", "/"}:
        raise ValueError("unsupported interval operation")
    try:
        a = _decode(left["lower"], left["upper"], left["error"])
        b = _decode(right["lower"], right["upper"], right["error"])
    except (ValueError, TypeError, KeyError):
        return INVALID
    if op == "/":
        b = [reciprocal for part in b for reciprocal in _reciprocal(part)]
    result = []
    for alo, ahi in a:
        for blo, bhi in b:
            if op == "+":
                result.append((alo + blo, ahi + bhi))
            elif op == "-":
                result.append((alo - bhi, ahi - blo))
            else:
                result.append(_multiply((alo, ahi), (blo, bhi)))
    return _encode(result)
