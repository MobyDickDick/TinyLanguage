# AC range conversion attempt log

- Timestamp (UTC): `2026-03-08T18:53:40.385219+00:00`
- Range: `AC0800..AC0884`
- Iterations: `128`
- Input count: `105`

## Environment

- Python: `3.14.2`
- Executable: `C:\Users\marku\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- Platform: `Windows-11-10.0.26200-SP0`
- Runtime path override: `C:\Users\marku\myCloud\TinyLanguage\tools\..\vendor\converter_runtime`

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
- Exit code: `1`
- Duration (s): `1.097`

### Converter stdout

```text
OpenCV bindings requires "numpy" package.
Install it via command:
    pip install numpy
```

### Converter stderr

```text
Traceback (most recent call last):
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5852, in <module>
    raise SystemExit(main())
                     ~~~~^^
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5838, in main
    out_dir = convert_range(
        args.folder_path,
    ...<5 lines>...
        args.debug_element_diff_dir,
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5164, in convert_range
    row = _convert_one(filename, iteration_budget=base_iterations, badge_rounds=6)
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 5127, in _convert_one
    res = run_iteration_pipeline(
        image_path,
    ...<7 lines>...
        badge_validation_rounds=max(1, int(badge_rounds)),
    )
  File "C:\Users\marku\myCloud\TinyLanguage\src\image_composite_converter.py", line 4318, in run_iteration_pipeline
    raise RuntimeError(
    ...<2 lines>...
    )
RuntimeError: Required image dependencies are missing: cv2, numpy. Install dependencies before running the conversion pipeline.
```
