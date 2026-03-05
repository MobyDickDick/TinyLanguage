# AC range conversion attempt log

- Timestamp (UTC): `2026-03-05T22:02:45.897351+00:00`
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
- Exit code: `1`
- Duration (s): `1.39`

### Converter stdout

```text

--- Verarbeite AC0847_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0884_L.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0881_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe, SEMANTIC: senkrechter Strich hinter dem Kreis

--- Verarbeite AC0833_L.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich oben vom Kreis
```

### Converter stderr

```text
Traceback (most recent call last):
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5338, in <module>
    raise SystemExit(main())
                     ~~~~^^
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5324, in main
    out_dir = convert_range(
        args.folder_path,
    ...<5 lines>...
        args.debug_element_diff_dir,
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 4680, in convert_range
    transferred, _detail = _try_template_transfer(
                           ~~~~~~~~~~~~~~~~~~~~~~^
        target_row=row,
        ^^^^^^^^^^^^^^^
    ...<4 lines>...
        rng=rng,
        ^^^^^^^^
    )
    ^
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 4536, in _try_template_transfer
    candidate_svg = Action.generate_badge_svg(w, h, candidate_params)
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 1831, in generate_badge_svg
    f'fill="{Action.grayhex(p["fill_gray"])}" stroke="{Action.grayhex(p["stroke_gray"])}" '
                            ~^^^^^^^^^^^^^
KeyError: 'fill_gray'
```
