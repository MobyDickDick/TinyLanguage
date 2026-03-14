# Statistik: Rekonvertierung Bild → SVG

Datengrundlage: `artifacts/converted_symbols/optimized_roundtrip/best_per_image.csv`.

## Gesamtüberblick

- Ausgewertete Bilder: **35**
- Optimierungs-Läufe genutzt (`max_iter > 0`): **14/35** (40.0%)
- Durchschnitt MAE (RGB): **31.642**
- Median MAE (RGB): **27.918**
- Durchschnitt RMSE (RGB): **50.912**
- Median RMSE (RGB): **49.424**
- Durchschnitt exakter Pixelanteil: **37.77%**
- Median exakter Pixelanteil: **41.87%**

## Verteilung exakter Pixel

| Klasse | Anzahl | Anteil |
|---|---:|---:|
| Sehr gut (>=45% exakte Pixel) | 12 | 34.3% |
| Mittel (35-45% exakte Pixel) | 16 | 45.7% |
| Schwach (<35% exakte Pixel) | 7 | 20.0% |

## Quantile

| Metrik | P10 | P50 | P90 |
|---|---:|---:|---:|
| MAE | 24.823 | 27.918 | 47.834 |
| RMSE | 44.325 | 49.424 | 62.284 |
| Exakte Pixel | 15.20% | 41.87% | 46.56% |

## Beste und schwächste Rekonvertierung

- Beste Exaktquote: **AC0842** mit **48.00%** exakten Pixeln.
- Schwächste Exaktquote: **AC0840** mit **14.44%** exakten Pixeln.

## 10 schwierigste Bilder (nach MAE)

| Code | MAE | RMSE | Exakte Pixel | max_iter |
|---|---:|---:|---:|---:|
| AC0850 | 54.362 | 73.052 | 15.33% | 0 |
| AC0840 | 52.971 | 72.057 | 14.44% | 0 |
| AC0870 | 49.762 | 63.049 | 14.44% | 120 |
| AC0820 | 47.874 | 60.604 | 14.56% | 120 |
| AC0835 | 47.774 | 61.640 | 16.32% | 120 |
| AC0845 | 44.698 | 56.768 | 16.80% | 120 |
| AC0800 | 43.694 | 62.713 | 15.11% | 0 |
| AC0843 | 29.739 | 52.351 | 45.33% | 0 |
| AC0863 | 29.633 | 52.731 | 45.16% | 0 |
| AC0861 | 29.469 | 48.019 | 41.51% | 120 |
