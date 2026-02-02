# Julia Subset Target: Statistics

This document defines the initial Julia-inspired subset that TinyLanguage will
target first. The scope focuses on the `Statistics` module because it is
compact, widely used, and enables meaningful numeric tests quickly.

## Goals

- Provide a TinyLanguage `Statistics` namespace with a Julia-like API surface.
- Keep the first milestone small enough to implement and test thoroughly.
- Document signatures and usage examples for every function in scope.

## Data Model Assumptions

- Functions operate on numeric arrays allocated via `new[...]`.
- Inputs must contain at least one element unless noted otherwise.
- All functions return `Num` values (floating point where necessary).

## Functions in Scope

### `Statistics.mean(values)`

**Signature:** `fn mean(values) -> Num`

**Behavior:** Returns the arithmetic mean of the values.

**Example:**

```tiny
def values = new[1, 2, 3, 4];
def avg = Statistics.mean(values); // -> 2.5
```

### `Statistics.std(values)`

**Signature:** `fn std(values) -> Num`

**Behavior:** Returns the population standard deviation (Julia: `std(values; corrected=false)`).

**Example:**

```tiny
def values = new[2, 4, 4, 4, 5, 5, 7, 9];
def sigma = Statistics.std(values); // -> 2.0
```

### `Statistics.var(values)`

**Signature:** `fn var(values) -> Num`

**Behavior:** Returns the population variance (Julia: `var(values; corrected=false)`).

**Example:**

```tiny
def values = new[1, 2, 3];
def variance = Statistics.var(values); // -> 0.666...
```

### `Statistics.minimum(values)`

**Signature:** `fn minimum(values) -> Num`

**Behavior:** Returns the smallest value.

**Example:**

```tiny
def values = new[4, 2, 9];
def min_val = Statistics.minimum(values); // -> 2
```

### `Statistics.maximum(values)`

**Signature:** `fn maximum(values) -> Num`

**Behavior:** Returns the largest value.

**Example:**

```tiny
def values = new[4, 2, 9];
def max_val = Statistics.maximum(values); // -> 9
```

### `Statistics.median(values)`

**Signature:** `fn median(values) -> Num`

**Behavior:** Returns the median value. For even-sized inputs, returns the mean
of the two middle elements after sorting.

**Example:**

```tiny
def values = new[1, 5, 2, 4];
def med = Statistics.median(values); // -> 3.0
```

## Compatibility Notes (Initial)

- All functions assume numeric arrays; non-numeric values are runtime errors.
- Empty arrays should raise a descriptive error rather than returning `NaN`.
- The first implementation mirrors Julia's population statistics defaults to
  avoid extra parameters in the TinyLanguage API.
