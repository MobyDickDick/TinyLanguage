# AC range conversion attempt log

- Timestamp (UTC): `2026-02-27T18:24:19.964040+00:00`
- Range: `AC0800..AC0884`
- Iterations: `8`
- Input count: `105`

## Environment

- Python: `3.14.2`
- Executable: `C:\Users\marku\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- Platform: `Windows-11-10.0.26200-SP0`

## Dependencies

- cv2: `True`
- numpy: `True`
- fitz: `True`

## Command

```bash
C:\Users\marku\AppData\Local\Python\pythoncore-3.14-64\python.exe src/image_composite_converter.py artifacts\images_to_convert artifacts/images_to_convert/nonexistent.csv 8 --start AC0800 --end AC0884
```

## Result

- Ran conversion: `true`
- Exit code: `0`
- Duration (s): `2.302`

### Converter stdout

```text

--- Verarbeite AC0800_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0800, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.07
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.07
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.07
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.07
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.07
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.07
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.07
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.07
-> Bester Match in Iteration 1 (Fehler auf 31.07 reduziert)

--- Verarbeite AC0800_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0800, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.61
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.61
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.61
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.61
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.61
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.61
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.61
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.61
-> Bester Match in Iteration 1 (Fehler auf 30.61 reduziert)

--- Verarbeite AC0800_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0800, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.42
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.42
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.42
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.42
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.42
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.42
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.42
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.42
-> Bester Match in Iteration 1 (Fehler auf 30.42 reduziert)

--- Verarbeite AC0811_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0811, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 20.98
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 20.98
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 20.98
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 20.98
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 20.98
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 20.98
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 20.98
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 20.98
-> Bester Match in Iteration 1 (Fehler auf 20.98 reduziert)

--- Verarbeite AC0811_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0811, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 22.57
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 22.57
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 22.57
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 22.57
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 22.57
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 22.57
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 22.57
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 22.57
-> Bester Match in Iteration 1 (Fehler auf 22.57 reduziert)

--- Verarbeite AC0811_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0811, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 22.87
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 22.87
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 22.87
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 22.87
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 22.87
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 22.87
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 22.87
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 22.87
-> Bester Match in Iteration 1 (Fehler auf 22.87 reduziert)

--- Verarbeite AC0812_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0812, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 22.16
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 22.16
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 22.16
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 22.16
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 22.16
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 22.16
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 22.16
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 22.16
-> Bester Match in Iteration 1 (Fehler auf 22.16 reduziert)

--- Verarbeite AC0812_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0812, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 23.37
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 23.37
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 23.37
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 23.37
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 23.37
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 23.37
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 23.37
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 23.37
-> Bester Match in Iteration 1 (Fehler auf 23.37 reduziert)

--- Verarbeite AC0812_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0812, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 24.14
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 24.14
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 24.14
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 24.14
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 24.14
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 24.14
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 24.14
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 24.14
-> Bester Match in Iteration 1 (Fehler auf 24.14 reduziert)

--- Verarbeite AC0813_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0813, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 21.55
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 21.55
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 21.55
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 21.55
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 21.55
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 21.55
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 21.55
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 21.55
-> Bester Match in Iteration 1 (Fehler auf 21.55 reduziert)

--- Verarbeite AC0813_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0813, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 23.03
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 23.03
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 23.03
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 23.03
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 23.03
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 23.03
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 23.03
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 23.03
-> Bester Match in Iteration 1 (Fehler auf 23.03 reduziert)

--- Verarbeite AC0813_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0813, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 24.47
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 24.47
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 24.47
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 24.47
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 24.47
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 24.47
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 24.47
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 24.47
-> Bester Match in Iteration 1 (Fehler auf 24.47 reduziert)

--- Verarbeite AC0814_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0814, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 22.28
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 22.28
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 22.28
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 22.28
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 22.28
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 22.28
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 22.28
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 22.28
-> Bester Match in Iteration 1 (Fehler auf 22.28 reduziert)

--- Verarbeite AC0814_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0814, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 23.36
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 23.36
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 23.36
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 23.36
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 23.36
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 23.36
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 23.36
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 23.36
-> Bester Match in Iteration 1 (Fehler auf 23.36 reduziert)

--- Verarbeite AC0814_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0814, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 24.03
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 24.03
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 24.03
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 24.03
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 24.03
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 24.03
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 24.03
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 24.03
-> Bester Match in Iteration 1 (Fehler auf 24.03 reduziert)

--- Verarbeite AC0820_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0820, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 42.30
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 42.30
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 42.30
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 42.30
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 42.30
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 42.30
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 42.30
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 42.30
-> Bester Match in Iteration 1 (Fehler auf 42.30 reduziert)

--- Verarbeite AC0820_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0820, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 42.99
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 42.99
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 42.99
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 42.99
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 42.99
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 42.99
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 42.99
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 42.99
-> Bester Match in Iteration 1 (Fehler auf 42.99 reduziert)

--- Verarbeite AC0820_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0820, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 43.29
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 43.29
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 43.29
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 43.29
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 43.29
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 43.29
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 43.29
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 43.29
-> Bester Match in Iteration 1 (Fehler auf 43.29 reduziert)

--- Verarbeite AC0831_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0831, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 28.78
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 28.78
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 28.78
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 28.78
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 28.78
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 28.78
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 28.78
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 28.78
-> Bester Match in Iteration 1 (Fehler auf 28.78 reduziert)

--- Verarbeite AC0831_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0831, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.18
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.18
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.18
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.18
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.18
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.18
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.18
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.18
-> Bester Match in Iteration 1 (Fehler auf 31.18 reduziert)

--- Verarbeite AC0831_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0831, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.51
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.51
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.51
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.51
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.51
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.51
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.51
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.51
-> Bester Match in Iteration 1 (Fehler auf 32.51 reduziert)

--- Verarbeite AC0832_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0832, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 28.49
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 28.49
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 28.49
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 28.49
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 28.49
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 28.49
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 28.49
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 28.49
-> Bester Match in Iteration 1 (Fehler auf 28.49 reduziert)

--- Verarbeite AC0832_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0832, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.23
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.23
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.23
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.23
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.23
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.23
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.23
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.23
-> Bester Match in Iteration 1 (Fehler auf 30.23 reduziert)

--- Verarbeite AC0832_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0832, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.14
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.14
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.14
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.14
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.14
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.14
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.14
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.14
-> Bester Match in Iteration 1 (Fehler auf 32.14 reduziert)

--- Verarbeite AC0833_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0833, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 27.30
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 27.30
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 27.30
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 27.30
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 27.30
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 27.30
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 27.30
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 27.30
-> Bester Match in Iteration 1 (Fehler auf 27.30 reduziert)

--- Verarbeite AC0833_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0833, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 29.12
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 29.12
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 29.12
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 29.12
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 29.12
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 29.12
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 29.12
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 29.12
-> Bester Match in Iteration 1 (Fehler auf 29.12 reduziert)

--- Verarbeite AC0833_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0833, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 29.98
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 29.98
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 29.98
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 29.98
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 29.98
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 29.98
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 29.98
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 29.98
-> Bester Match in Iteration 1 (Fehler auf 29.98 reduziert)

--- Verarbeite AC0834_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0834, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 28.92
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 28.92
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 28.92
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 28.92
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 28.92
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 28.92
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 28.92
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 28.92
-> Bester Match in Iteration 1 (Fehler auf 28.92 reduziert)

--- Verarbeite AC0834_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0834, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.62
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.62
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.62
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.62
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.62
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.62
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.62
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.62
-> Bester Match in Iteration 1 (Fehler auf 30.62 reduziert)

--- Verarbeite AC0834_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0834, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.95
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.95
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.95
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.95
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.95
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.95
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.95
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.95
-> Bester Match in Iteration 1 (Fehler auf 32.95 reduziert)

--- Verarbeite AC0835_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0835, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 45.80
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 45.80
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 45.80
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 45.80
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 45.80
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 45.80
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 45.80
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 45.80
-> Bester Match in Iteration 1 (Fehler auf 45.80 reduziert)

--- Verarbeite AC0835_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0835, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 46.16
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 46.16
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 46.16
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 46.16
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 46.16
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 46.16
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 46.16
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 46.16
-> Bester Match in Iteration 1 (Fehler auf 46.16 reduziert)

--- Verarbeite AC0835_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0835, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 47.04
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 47.04
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 47.04
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 47.04
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 47.04
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 47.04
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 47.04
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 47.04
-> Bester Match in Iteration 1 (Fehler auf 47.04 reduziert)

--- Verarbeite AC0836_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0836, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.44
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.44
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.44
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.44
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.44
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.44
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.44
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.44
-> Bester Match in Iteration 1 (Fehler auf 30.44 reduziert)

--- Verarbeite AC0836_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0836, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.92
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.92
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.92
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.92
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.92
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.92
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.92
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.92
-> Bester Match in Iteration 1 (Fehler auf 32.92 reduziert)

--- Verarbeite AC0836_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0836, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 34.27
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 34.27
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 34.27
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 34.27
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 34.27
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 34.27
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 34.27
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 34.27
-> Bester Match in Iteration 1 (Fehler auf 34.27 reduziert)

--- Verarbeite AC0837_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0837, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.63
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.63
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.63
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.63
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.63
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.63
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.63
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.63
-> Bester Match in Iteration 1 (Fehler auf 30.63 reduziert)

--- Verarbeite AC0837_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0837, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.45
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.45
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.45
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.45
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.45
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.45
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.45
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.45
-> Bester Match in Iteration 1 (Fehler auf 32.45 reduziert)

--- Verarbeite AC0837_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0837, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 34.35
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 34.35
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 34.35
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 34.35
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 34.35
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 34.35
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 34.35
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 34.35
-> Bester Match in Iteration 1 (Fehler auf 34.35 reduziert)

--- Verarbeite AC0838_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0838, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 29.17
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 29.17
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 29.17
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 29.17
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 29.17
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 29.17
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 29.17
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 29.17
-> Bester Match in Iteration 1 (Fehler auf 29.17 reduziert)

--- Verarbeite AC0838_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0838, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.34
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.34
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.34
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.34
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.34
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.34
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.34
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.34
-> Bester Match in Iteration 1 (Fehler auf 31.34 reduziert)

--- Verarbeite AC0838_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0838, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.15
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.15
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.15
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.15
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.15
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.15
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.15
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.15
-> Bester Match in Iteration 1 (Fehler auf 31.15 reduziert)

--- Verarbeite AC0839_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0839, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.10
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.10
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.10
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.10
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.10
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.10
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.10
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.10
-> Bester Match in Iteration 1 (Fehler auf 30.10 reduziert)

--- Verarbeite AC0839_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0839, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.87
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.87
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.87
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.87
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.87
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.87
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.87
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.87
-> Bester Match in Iteration 1 (Fehler auf 31.87 reduziert)

--- Verarbeite AC0839_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0839, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.56
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.56
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.56
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.56
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.56
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.56
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.56
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.56
-> Bester Match in Iteration 1 (Fehler auf 33.56 reduziert)

--- Verarbeite AC0840_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0840, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 49.20
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 49.20
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 49.20
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 49.20
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 49.20
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 49.20
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 49.20
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 49.20
-> Bester Match in Iteration 1 (Fehler auf 49.20 reduziert)

--- Verarbeite AC0840_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0840, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 49.37
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 49.37
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 49.37
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 49.37
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 49.37
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 49.37
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 49.37
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 49.37
-> Bester Match in Iteration 1 (Fehler auf 49.37 reduziert)

--- Verarbeite AC0840_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0840, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 50.47
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 50.47
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 50.47
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 50.47
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 50.47
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 50.47
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 50.47
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 50.47
-> Bester Match in Iteration 1 (Fehler auf 50.47 reduziert)

--- Verarbeite AC0841_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0841, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.08
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.08
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.08
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.08
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.08
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.08
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.08
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.08
-> Bester Match in Iteration 1 (Fehler auf 32.08 reduziert)

--- Verarbeite AC0841_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0841, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 34.16
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 34.16
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 34.16
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 34.16
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 34.16
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 34.16
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 34.16
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 34.16
-> Bester Match in Iteration 1 (Fehler auf 34.16 reduziert)

--- Verarbeite AC0841_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0841, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 36.15
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 36.15
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 36.15
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 36.15
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 36.15
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 36.15
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 36.15
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 36.15
-> Bester Match in Iteration 1 (Fehler auf 36.15 reduziert)

--- Verarbeite AC0842_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0842, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.59
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.59
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.59
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.59
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.59
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.59
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.59
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.59
-> Bester Match in Iteration 1 (Fehler auf 31.59 reduziert)

--- Verarbeite AC0842_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0842, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.31
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.31
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.31
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.31
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.31
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.31
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.31
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.31
-> Bester Match in Iteration 1 (Fehler auf 33.31 reduziert)

--- Verarbeite AC0842_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0842, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 35.26
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 35.26
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 35.26
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 35.26
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 35.26
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 35.26
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 35.26
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 35.26
-> Bester Match in Iteration 1 (Fehler auf 35.26 reduziert)

--- Verarbeite AC0843_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0843, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.02
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.02
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.02
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.02
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.02
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.02
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.02
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.02
-> Bester Match in Iteration 1 (Fehler auf 31.02 reduziert)

--- Verarbeite AC0843_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0843, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.13
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.13
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.13
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.13
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.13
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.13
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.13
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.13
-> Bester Match in Iteration 1 (Fehler auf 33.13 reduziert)

--- Verarbeite AC0843_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0843, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.04
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.04
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.04
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.04
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.04
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.04
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.04
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.04
-> Bester Match in Iteration 1 (Fehler auf 33.04 reduziert)

--- Verarbeite AC0844_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0844, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.56
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.56
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.56
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.56
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.56
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.56
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.56
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.56
-> Bester Match in Iteration 1 (Fehler auf 33.56 reduziert)

--- Verarbeite AC0844_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0844, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 35.61
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 35.61
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 35.61
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 35.61
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 35.61
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 35.61
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 35.61
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 35.61
-> Bester Match in Iteration 1 (Fehler auf 35.61 reduziert)

--- Verarbeite AC0844_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0844, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 37.67
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 37.67
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 37.67
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 37.67
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 37.67
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 37.67
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 37.67
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 37.67
-> Bester Match in Iteration 1 (Fehler auf 37.67 reduziert)

--- Verarbeite AC0845_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0845, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 52.48
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 52.48
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 52.48
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 52.48
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 52.48
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 52.48
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 52.48
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 52.48
-> Bester Match in Iteration 1 (Fehler auf 52.48 reduziert)

--- Verarbeite AC0845_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0845, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 52.76
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 52.76
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 52.76
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 52.76
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 52.76
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 52.76
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 52.76
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 52.76
-> Bester Match in Iteration 1 (Fehler auf 52.76 reduziert)

--- Verarbeite AC0845_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0845, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 53.64
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 53.64
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 53.64
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 53.64
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 53.64
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 53.64
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 53.64
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 53.64
-> Bester Match in Iteration 1 (Fehler auf 53.64 reduziert)

--- Verarbeite AC0846_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0846, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 34.52
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 34.52
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 34.52
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 34.52
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 34.52
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 34.52
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 34.52
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 34.52
-> Bester Match in Iteration 1 (Fehler auf 34.52 reduziert)

--- Verarbeite AC0846_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0846, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 36.71
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 36.71
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 36.71
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 36.71
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 36.71
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 36.71
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 36.71
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 36.71
-> Bester Match in Iteration 1 (Fehler auf 36.71 reduziert)

--- Verarbeite AC0846_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0846, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 38.00
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 38.00
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 38.00
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 38.00
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 38.00
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 38.00
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 38.00
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 38.00
-> Bester Match in Iteration 1 (Fehler auf 38.00 reduziert)

--- Verarbeite AC0847_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0847, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.25
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.25
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.25
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.25
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.25
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.25
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.25
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.25
-> Bester Match in Iteration 1 (Fehler auf 33.25 reduziert)

--- Verarbeite AC0847_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0847, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 35.95
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 35.95
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 35.95
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 35.95
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 35.95
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 35.95
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 35.95
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 35.95
-> Bester Match in Iteration 1 (Fehler auf 35.95 reduziert)

--- Verarbeite AC0847_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0847, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 37.62
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 37.62
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 37.62
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 37.62
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 37.62
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 37.62
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 37.62
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 37.62
-> Bester Match in Iteration 1 (Fehler auf 37.62 reduziert)

--- Verarbeite AC0848_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0848, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.78
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.78
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.78
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.78
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.78
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.78
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.78
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.78
-> Bester Match in Iteration 1 (Fehler auf 32.78 reduziert)

--- Verarbeite AC0848_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0848, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 34.37
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 34.37
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 34.37
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 34.37
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 34.37
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 34.37
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 34.37
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 34.37
-> Bester Match in Iteration 1 (Fehler auf 34.37 reduziert)

--- Verarbeite AC0848_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0848, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 36.09
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 36.09
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 36.09
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 36.09
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 36.09
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 36.09
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 36.09
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 36.09
-> Bester Match in Iteration 1 (Fehler auf 36.09 reduziert)

--- Verarbeite AC0849_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0849, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.60
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.60
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.60
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.60
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.60
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.60
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.60
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.60
-> Bester Match in Iteration 1 (Fehler auf 33.60 reduziert)

--- Verarbeite AC0849_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0849, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 35.13
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 35.13
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 35.13
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 35.13
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 35.13
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 35.13
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 35.13
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 35.13
-> Bester Match in Iteration 1 (Fehler auf 35.13 reduziert)

--- Verarbeite AC0849_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0849, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 36.79
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 36.79
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 36.79
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 36.79
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 36.79
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 36.79
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 36.79
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 36.79
-> Bester Match in Iteration 1 (Fehler auf 36.79 reduziert)

--- Verarbeite AC0850_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0850, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 45.45
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 45.45
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 45.45
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 45.45
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 45.45
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 45.45
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 45.45
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 45.45
-> Bester Match in Iteration 1 (Fehler auf 45.45 reduziert)

--- Verarbeite AC0850_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0850, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 45.50
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 45.50
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 45.50
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 45.50
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 45.50
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 45.50
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 45.50
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 45.50
-> Bester Match in Iteration 1 (Fehler auf 45.50 reduziert)

--- Verarbeite AC0850_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0850, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 45.78
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 45.78
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 45.78
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 45.78
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 45.78
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 45.78
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 45.78
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 45.78
-> Bester Match in Iteration 1 (Fehler auf 45.78 reduziert)

--- Verarbeite AC0861_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0861, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.64
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.64
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.64
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.64
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.64
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.64
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.64
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.64
-> Bester Match in Iteration 1 (Fehler auf 30.64 reduziert)

--- Verarbeite AC0861_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0861, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.94
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.94
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.94
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.94
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.94
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.94
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.94
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.94
-> Bester Match in Iteration 1 (Fehler auf 32.94 reduziert)

--- Verarbeite AC0861_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0861, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.99
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.99
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.99
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.99
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.99
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.99
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.99
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.99
-> Bester Match in Iteration 1 (Fehler auf 33.99 reduziert)

--- Verarbeite AC0862_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0862, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 29.36
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 29.36
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 29.36
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 29.36
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 29.36
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 29.36
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 29.36
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 29.36
-> Bester Match in Iteration 1 (Fehler auf 29.36 reduziert)

--- Verarbeite AC0862_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0862, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.70
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.70
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.70
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.70
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.70
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.70
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.70
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.70
-> Bester Match in Iteration 1 (Fehler auf 30.70 reduziert)

--- Verarbeite AC0862_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0862, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.14
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.14
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.14
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.14
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.14
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.14
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.14
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.14
-> Bester Match in Iteration 1 (Fehler auf 33.14 reduziert)

--- Verarbeite AC0863_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0863, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 29.70
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 29.70
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 29.70
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 29.70
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 29.70
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 29.70
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 29.70
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 29.70
-> Bester Match in Iteration 1 (Fehler auf 29.70 reduziert)

--- Verarbeite AC0863_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0863, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.10
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.10
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.10
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.10
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.10
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.10
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.10
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.10
-> Bester Match in Iteration 1 (Fehler auf 31.10 reduziert)

--- Verarbeite AC0863_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0863, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 31.05
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 31.05
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 31.05
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 31.05
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 31.05
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 31.05
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 31.05
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 31.05
-> Bester Match in Iteration 1 (Fehler auf 31.05 reduziert)

--- Verarbeite AC0864_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0864, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.03
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.03
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.03
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.03
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.03
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.03
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.03
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.03
-> Bester Match in Iteration 1 (Fehler auf 32.03 reduziert)

--- Verarbeite AC0864_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0864, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 33.22
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 33.22
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 33.22
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 33.22
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 33.22
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 33.22
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 33.22
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 33.22
-> Bester Match in Iteration 1 (Fehler auf 33.22 reduziert)

--- Verarbeite AC0864_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0864, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 35.70
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 35.70
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 35.70
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 35.70
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 35.70
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 35.70
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 35.70
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 35.70
-> Bester Match in Iteration 1 (Fehler auf 35.70 reduziert)

--- Verarbeite AC0870_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0870_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0870_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0881_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0881_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0881_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0882_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0882_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0882_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0883_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0883, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 26.67
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 26.67
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 26.67
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 26.67
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 26.67
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 26.67
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 26.67
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 26.67
-> Bester Match in Iteration 1 (Fehler auf 26.67 reduziert)

--- Verarbeite AC0883_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0883, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 28.09
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 28.09
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 28.09
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 28.09
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 28.09
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 28.09
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 28.09
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 28.09
-> Bester Match in Iteration 1 (Fehler auf 28.09 reduziert)

--- Verarbeite AC0883_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0883, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 28.40
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 28.40
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 28.40
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 28.40
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 28.40
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 28.40
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 28.40
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 28.40
-> Bester Match in Iteration 1 (Fehler auf 28.40 reduziert)

--- Verarbeite AC0884_L.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0884, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 29.13
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 29.13
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 29.13
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 29.13
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 29.13
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 29.13
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 29.13
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 29.13
-> Bester Match in Iteration 1 (Fehler auf 29.13 reduziert)

--- Verarbeite AC0884_M.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0884, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 30.92
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 30.92
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 30.92
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 30.92
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 30.92
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 30.92
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 30.92
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 30.92
-> Bester Match in Iteration 1 (Fehler auf 30.92 reduziert)

--- Verarbeite AC0884_S.jpg ---
Befehl erkannt: OBEN: Geschnitten aus Originaldatei AC0884, UNTEN: Parametrisch generiertes Viereck mit Kreuz
  [Iter 1/8] Epsilon=0.0500 -> Diff-Fehler: 32.29
  [Iter 2/8] Epsilon=0.0429 -> Diff-Fehler: 32.29
  [Iter 3/8] Epsilon=0.0359 -> Diff-Fehler: 32.29
  [Iter 4/8] Epsilon=0.0288 -> Diff-Fehler: 32.29
  [Iter 5/8] Epsilon=0.0217 -> Diff-Fehler: 32.29
  [Iter 6/8] Epsilon=0.0146 -> Diff-Fehler: 32.29
  [Iter 7/8] Epsilon=0.0076 -> Diff-Fehler: 32.29
  [Iter 8/8] Epsilon=0.0005 -> Diff-Fehler: 32.29
-> Bester Match in Iteration 1 (Fehler auf 32.29 reduziert)

Abgeschlossen! Ausgaben unter: artifacts\images_to_convert\Iterated_SVGs
```

### Converter stderr

```text

```
