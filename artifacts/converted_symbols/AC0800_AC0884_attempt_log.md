# AC range conversion attempt log

- Timestamp (UTC): `2026-02-28T19:29:28.027962+00:00`
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
- Exit code: `1`
- Duration (s): `1.76`

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
```

### Converter stderr

```text
Traceback (most recent call last):
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 1913, in <module>
    raise SystemExit(main())
                     ~~~~^^
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 1900, in main
    out_dir = convert_range(
        args.folder_path,
    ...<4 lines>...
        args.debug_ac0811_dir,
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 1616, in convert_range
    res = run_iteration_pipeline(
        image_path,
    ...<5 lines>...
        debug_ac0811_dir,
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 1491, in run_iteration_pipeline
    badge_params = Action.make_badge_params(w, h, perc.base_name, perc.img)
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 883, in make_badge_params
    return Action._apply_co2_label(Action._fit_ac0812_params_from_image(img, defaults))
                                   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 424, in _fit_ac0812_params_from_image
    params = Action._fit_semantic_badge_from_image(img, defaults)
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 783, in _fit_semantic_badge_from_image
    Action._center_glyph_bbox(params)
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 589, in _center_glyph_bbox
    glyph_width = (xmax - xmin) * params["s"]
                                  ~~~~~~^^^^^
KeyError: 's'
```
