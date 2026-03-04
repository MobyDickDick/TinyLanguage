# AC range conversion attempt log

- Timestamp (UTC): `2026-03-04T20:03:17.255624+00:00`
- Range: `AC0800..AC0884`
- Iterations: `8`
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
C:\Users\marku\AppData\Local\Python\pythoncore-3.14-64\python.exe src/image_composite_converter.py artifacts\images_to_convert artifacts/images_to_convert/nonexistent.csv 8 --start AC0800 --end AC0884
```

## Result

- Ran conversion: `true`
- Exit code: `0`
- Duration (s): `29.62`

### Converter stdout

```text

--- Verarbeite AC0800_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe

--- Verarbeite AC0800_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe

--- Verarbeite AC0800_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe

--- Verarbeite AC0811_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0811_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0811_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0812_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0812_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0812_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0813_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0813_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0813_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0814_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0814_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0814_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis ohne Buchstabe, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0820_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0820_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0820_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2

--- Verarbeite AC0831_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0831_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0831_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0832_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0832_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0832_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0833_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0833_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0833_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0834_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0834_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0834_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0835_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0835_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0835_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC

--- Verarbeite AC0836_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0836_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0836_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0837_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0837_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0837_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: waagrechter Strich links vom Kreis

--- Verarbeite AC0838_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0838_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0838_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: senkrechter Strich oben vom Kreis

--- Verarbeite AC0839_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0839_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0839_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: waagrechter Strich rechts vom Kreis

--- Verarbeite AC0840_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0840_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0840_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0841_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0841_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0841_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0842_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0842_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0842_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0843_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0843_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0843_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0844_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0844_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0844_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0845_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0845_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0845_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0846_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0846_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0846_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0847_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0847_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0847_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0848_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0848_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0848_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0849_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0849_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0849_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0850_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0850_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0850_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0861_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0861_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0861_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0862_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0862_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0862_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0863_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0863_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0863_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0864_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0864_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0864_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

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
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0883_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0883_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0884_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0884_M.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0884_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

Abgeschlossen! Ausgaben unter: C:\Users\marku\myCloud\TinyLanguage\artifacts\converted_symbols
```

### Converter stderr

```text

```
