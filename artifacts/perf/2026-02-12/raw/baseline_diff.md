# Baseline diff (threshold 1.15x)


| case | backend | baseline_ms | current_avg_ms | slowdown_ratio |
| --- | --- | ---: | ---: | ---: |
| heap_roundtrip | native | 340.18 | 539.99 | 1.59x |
| map_operations | interpreter | 187.51 | 295.64 | 1.58x |
| heap_roundtrip | interpreter | 567.65 | 888.34 | 1.56x |
| map_operations | native | 106.87 | 148.58 | 1.39x |
| tight_loop | interpreter | 339.00 | 461.94 | 1.36x |
| recursive_calls | interpreter | 221.34 | 299.35 | 1.35x |
| recursive_calls | native-python-bytecode | 28.37 | 37.55 | 1.32x |
| tight_loop | native | 136.53 | 172.07 | 1.26x |
| recursive_calls | native | 96.14 | 120.11 | 1.25x |
