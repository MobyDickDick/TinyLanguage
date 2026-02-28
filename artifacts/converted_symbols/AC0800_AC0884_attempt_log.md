# AC range conversion attempt log

- Timestamp (UTC): `2026-02-28T22:22:36.248904+00:00`
- Range: `AC0800..AC0800`
- Iterations: `1`
- Input count: `3`

## Environment

- Python: `3.10.19`
- Executable: `/root/.pyenv/versions/3.10.19/bin/python3`
- Platform: `Linux-6.12.47-x86_64-with-glibc2.39`
- Runtime path override: `(none)`

## Dependencies

- cv2: available=`False` version=`` origin=``
- numpy: available=`False` version=`` origin=``
- fitz: available=`False` version=`` origin=``

## Command

```bash
/root/.pyenv/versions/3.10.19/bin/python3 src/image_composite_converter.py artifacts/images_to_convert artifacts/images_to_convert/nonexistent.csv 1 --start AC0800 --end AC0800
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
