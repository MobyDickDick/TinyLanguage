# stdlib.math parity map

This parity map enumerates the subset of Python's `math` module that TinyLanguage
mirrors today. Each entry lists the Python API and the corresponding TinyLanguage
function or constant exposed by `stdlib.math`.

## Core constants

| Python `math` | TinyLanguage `stdlib.math` | Notes |
| --- | --- | --- |
| `math.pi` | `math.pi` | IEEE 754 double-precision constant. |
| `math.tau` | `math.tau` | Equivalent to `2 * pi`. |
| `math.e` | `math.e` | Euler's number. |

## Core functions

| Python `math` | TinyLanguage `stdlib.math` | Notes |
| --- | --- | --- |
| `math.fabs(x)` | `math.fabs(x)` | Delegates to `Math.abs`. |
| `math.sqrt(x)` | `math.sqrt(x)` | Delegates to `Math.sqrt`. |
| `math.pow(x, y)` | `math.pow(x, y)` | Delegates to `Math.pow`. |
| `math.floor(x)` | `math.floor(x)` | Delegates to `Math.floor`. |
| `math.ceil(x)` | `math.ceil(x)` | Delegates to `Math.ceil`. |
| `math.trunc(x)` | `math.trunc(x)` | Uses `Math.floor`/`Math.ceil` based on sign. |
| `math.copysign(x, y)` | `math.copysign(x, y)` | Sign match for `y < 0` (no `-0` distinction). |
| `math.degrees(x)` | `math.degrees(x)` | `x * 180 / pi`. |
| `math.radians(x)` | `math.radians(x)` | `x * pi / 180`. |
| `math.isclose(a, b)` | `math.isclose(a, b)` | Defaults to `rel_tol=1e-9`, `abs_tol=0`. |
| `math.isclose(a, b, rel_tol, abs_tol)` | `math.isclose_tol(a, b, rel_tol, abs_tol)` | Explicit tolerances. |

## TinyLanguage-specific helpers

| TinyLanguage `stdlib.math` | Notes |
| --- | --- |
| `math.round(x)` | Equivalent to Python's `round(x)` without the optional digits argument. |
| `math.round_digits(x, digits)` | Replacement for Python `round(x, ndigits)`. |
| `math.clamp(value, lower, upper)` | Clamp helper built on the native `Math` namespace. |
| `math.sign(x)` | Returns -1, 0, or 1 depending on the sign. |
| `math.max(a, b)` / `math.min(a, b)` | Two-argument `max`/`min` helpers. |
