# AC range conversion attempt log

- Timestamp (UTC): `2026-02-27T17:17:36.309056+00:00`
- Range: `AC0800..AC0884`
- Iterations: `8`
- Input count: `105`

## Environment

- Python: `3.10.19`
- Executable: `/root/.pyenv/versions/3.10.19/bin/python3`
- Platform: `Linux-6.12.47-x86_64-with-glibc2.39`

## Dependencies

- cv2: `False`
- numpy: `False`
- fitz: `False`

## Command

```bash
/root/.pyenv/versions/3.10.19/bin/python3 src/image_composite_converter.py artifacts/images_to_convert artifacts/images_to_convert/nonexistent.csv 8 --start AC0800 --end AC0884
```

## Result

- Ran conversion: `false`
- Reason: `missing dependencies`

## Suggested install commands

### Linux/macOS (bash)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy opencv-python-headless pymupdf
```

### Windows (PowerShell)
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install numpy opencv-python-headless pymupdf
```
