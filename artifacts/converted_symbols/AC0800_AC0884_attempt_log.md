# AC range conversion attempt log

- Timestamp (UTC): `2026-03-07T12:52:10.660939+00:00`
- Range: `AC0800..AC0884`
- Iterations: `128`
- Input count: `105`

## Environment

- Python: `3.14.2`
- Executable: `C:\Users\marku\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- Platform: `Windows-11-10.0.26200-SP0`
- Runtime path override: `(none)`

## Dependencies

- cv2: available=`True` version=`unknown` origin=`C:\Users\marku\AppData\Roaming\Python\Python314\site-packages\cv2\__init__.py`
- numpy: available=`True` version=`2.4.2` origin=`C:\Users\marku\AppData\Roaming\Python\Python314\site-packages\numpy\__init__.py`
- fitz: available=`True` version=`unknown` origin=`C:\Users\marku\AppData\Roaming\Python\Python314\site-packages\fitz\__init__.py`

## Command

```bash
C:\Users\marku\AppData\Local\Python\pythoncore-3.14-64\python.exe src/image_composite_converter.py artifacts\images_to_convert artifacts/images_to_convert/nonexistent.csv 128 --start AC0800 --end AC0884
```

## Result

- Ran conversion: `true`
- Exit code: `0`
- Duration (s): `58.954`

### Converter stdout

```text

--- Verarbeite AC0814_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0862_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0839_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0831_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0844_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0883_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0835_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0838_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0841_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0864_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0820_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0813_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0820_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0832_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0835_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0863_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0842_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0849_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0840_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0884_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0813_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0836_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0861_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0814_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0884_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0850_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0884_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0843_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0846_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0820_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0834_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0845_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0848_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0864_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0850_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0839_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0870_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0837_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0881_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0812_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0883_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0850_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0883_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0842_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0882_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0831_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0847_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0845_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0841_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0840_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0848_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0833_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0847_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0834_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0836_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0846_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0832_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0800_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0849_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0870_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0870_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0882_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0863_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0843_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0841_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0843_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0813_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0844_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0837_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0835_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0842_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0862_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0861_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0848_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0881_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0831_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0839_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0882_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0800_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0862_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0837_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0836_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0863_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0814_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0811_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0811_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0838_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0812_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0834_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0812_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0881_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0864_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0838_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0833_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0800_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0840_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0845_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0832_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0844_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0846_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0861_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0833_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0849_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0847_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0811_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Im Bild ist senkrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0800_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0835_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0820_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0882_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0835_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0870_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0870_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0820_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0881_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0882_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0835_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0820_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0882_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0835_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0882_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0835_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0835_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0870_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0800_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0881_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0870_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0820_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0882_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0870_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0835_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0870_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0881_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0882_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0835_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0820_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0835_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0800_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

--- Verarbeite AC0820_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0881_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0882_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0870_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0835_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0882_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0870_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe

--- Verarbeite AC0835_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0820_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0835_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0820_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0800_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden

Abgeschlossen! Ausgaben unter: C:\Users\marku\myCloud\TinyLanguage\artifacts\converted_symbols
```

### Converter stderr

```text

```
