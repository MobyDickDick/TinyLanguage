# AC range conversion attempt log

- Timestamp (UTC): `2026-03-06T11:48:59.768230+00:00`
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
- Duration (s): `1.66`

### Converter stdout

```text

--- Verarbeite AC0863_S.jpg ---
Befehl erkannt: Kein Compositing-Befehl gefunden
  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.

--- Verarbeite AC0833_M.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe CO_2, SEMANTIC: senkrechter Strich oben vom Kreis
[ERROR] Semantik-Abgleich fehlgeschlagen:
  - Beschreibung erwartet senkrechter Strich, im Bild aber nicht robust erkennbar
  - Im Bild ist waagrechter Strich erkennbar, aber nicht in der Beschreibung enthalten

--- Verarbeite AC0836_S.jpg ---
Befehl erkannt: SEMANTIC: Kreis + Buchstabe VOC, SEMANTIC: senkrechter Strich hinter dem Kreis
```

### Converter stderr

```text
Traceback (most recent call last):
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5504, in <module>
    raise SystemExit(main())
                     ~~~~^^
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5490, in main
    out_dir = convert_range(
        args.folder_path,
    ...<5 lines>...
        args.debug_element_diff_dir,
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 4816, in convert_range
    row = _convert_one(filename, iteration_budget=base_iterations, badge_rounds=6)
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 4779, in _convert_one
    res = run_iteration_pipeline(
        image_path,
    ...<7 lines>...
        badge_validation_rounds=max(1, int(badge_rounds)),
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 4100, in run_iteration_pipeline
    validation_logs = Action.validate_badge_by_elements(
        perc.img,
    ...<2 lines>...
        debug_out_dir=debug_dir,
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 3977, in validate_badge_by_elements
    width_changed = Action._optimize_element_width_bracket(img_orig, params, element, logs)
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 3527, in _optimize_element_width_bracket
    info = Action._element_width_key_and_bounds(element, params, w, h, img_orig=img_orig)
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 2806, in _element_width_key_and_bounds
    if min_dim > 22.0:
       ^^^^^^^
NameError: name 'min_dim' is not defined
```
