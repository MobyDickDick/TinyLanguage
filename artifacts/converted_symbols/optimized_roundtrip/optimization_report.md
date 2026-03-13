# JPEG→SVG→Raster Roundtrip Optimization

- Images evaluated: **35**
- Parameter sets evaluated: **5**
- Best-per-image average MAE: **7.136**
- Best-per-image average RMSE: **24.932**
- Best-per-image average exact pixel ratio: **89.41%**

## Parameter-set aggregate ranking

| Param set | Avg MAE | Avg RMSE | Avg exact pixels |
|---|---:|---:|---:|
| iter360_plat108_seed42 | 7.136 | 24.932 | 89.41% |
| iter480_plat144_seed42 | 7.136 | 24.932 | 89.41% |
| iter120_plat36_seed42 | 7.202 | 25.183 | 89.49% |
| iter240_plat72_seed42 | 7.202 | 25.183 | 89.49% |
| iter240_plat72_seed1337 | 7.202 | 25.183 | 89.49% |

## Worst 10 images after optimization

| Code | Source | MAE | RMSE | Exact pixels | Chosen params |
|---|---|---:|---:|---:|---|
| AC0820 | AC0820_L.jpg | 11.567 | 32.411 | 82.44% | iter=360, plateau=108, seed=42 |
| AC0835 | AC0835_L.jpg | 10.278 | 29.769 | 84.80% | iter=120, plateau=36, seed=42 |
| AC0845 | AC0845_L.jpg | 10.278 | 29.769 | 84.80% | iter=120, plateau=36, seed=42 |
| AC0800 | AC0800_L.jpg | 9.304 | 26.376 | 82.44% | iter=360, plateau=108, seed=42 |
| AC0840 | AC0840_L.jpg | 9.304 | 26.376 | 82.44% | iter=360, plateau=108, seed=42 |
| AC0850 | AC0850_L.jpg | 9.304 | 26.376 | 82.44% | iter=360, plateau=108, seed=42 |
| AC0870 | AC0870_L.jpg | 9.304 | 26.376 | 82.44% | iter=360, plateau=108, seed=42 |
| AC0813 | AC0813_L.jpg | 7.516 | 26.865 | 90.13% | iter=120, plateau=36, seed=42 |
| AC0833 | AC0833_L.jpg | 7.516 | 26.865 | 90.13% | iter=120, plateau=36, seed=42 |
| AC0838 | AC0838_L.jpg | 7.516 | 26.865 | 90.13% | iter=120, plateau=36, seed=42 |
