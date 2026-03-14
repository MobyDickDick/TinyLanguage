# JPEG→SVG→Raster Roundtrip Optimization

- Images evaluated: **35**
- Parameter sets evaluated: **5**
- Best-per-image average MAE: **31.642**
- Best-per-image average RMSE: **50.912**
- Best-per-image average exact pixel ratio: **37.77%**

## Parameter-set aggregate ranking

| Param set | Avg MAE | Avg RMSE | Avg exact pixels |
|---|---:|---:|---:|
| template_svg | 32.714 | 54.374 | 37.25% |
| iter120_plat36_seed42 | 33.940 | 50.922 | 38.23% |
| iter360_plat108_seed42 | 34.077 | 51.067 | 38.18% |
| iter240_plat72_seed42 | 34.084 | 51.059 | 38.16% |
| iter480_plat144_seed42 | 34.096 | 51.100 | 38.18% |
| iter240_plat72_seed1337 | 34.983 | 52.155 | 37.73% |

## Worst 10 images after optimization

| Code | Source | MAE | RMSE | Exact pixels | Chosen params |
|---|---|---:|---:|---:|---|
| AC0850 | AC0850_L.jpg | 54.362 | 73.052 | 15.33% | iter=0, plateau=0, seed=0 |
| AC0840 | AC0840_L.jpg | 52.971 | 72.057 | 14.44% | iter=0, plateau=0, seed=0 |
| AC0870 | AC0870_L.jpg | 49.762 | 63.049 | 14.44% | iter=120, plateau=36, seed=42 |
| AC0820 | AC0820_L.jpg | 47.874 | 60.604 | 14.56% | iter=120, plateau=36, seed=42 |
| AC0835 | AC0835_L.jpg | 47.774 | 61.640 | 16.32% | iter=120, plateau=36, seed=42 |
| AC0845 | AC0845_L.jpg | 44.698 | 56.768 | 16.80% | iter=120, plateau=36, seed=42 |
| AC0800 | AC0800_L.jpg | 43.694 | 62.713 | 15.11% | iter=0, plateau=0, seed=0 |
| AC0843 | AC0843_L.jpg | 29.739 | 52.351 | 45.33% | iter=0, plateau=0, seed=0 |
| AC0863 | AC0863_L.jpg | 29.633 | 52.731 | 45.16% | iter=0, plateau=0, seed=0 |
| AC0861 | AC0861_L.jpg | 29.469 | 48.019 | 41.51% | iter=120, plateau=36, seed=42 |
