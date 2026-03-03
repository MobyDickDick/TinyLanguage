@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

set "DEFAULT_FOLDER=%SCRIPT_DIR%artifacts\images_to_convert"
set "DEFAULT_CSV=%SCRIPT_DIR%artifacts\images_to_convert\nonexistent.csv"
set "DEFAULT_ITERATIONS=8"
set "DEFAULT_START=AC0800"
set "DEFAULT_END=AC0884"

if "%~1"=="" (
  echo [INFO] Keine Argumente uebergeben, verwende Standardlauf fuer repo-faehige Artefakte.
  echo [INFO] Ordner: "%DEFAULT_FOLDER%"
  echo [INFO] CSV: "%DEFAULT_CSV%"
  echo [INFO] Iterationen: %DEFAULT_ITERATIONS%, Bereich: %DEFAULT_START%..%DEFAULT_END%
  "%PYTHON_EXE%" "%SCRIPT_DIR%src\converter_runtime_bootstrap.py" ^
    --vendor-root "%SCRIPT_DIR%vendor\converter_runtime" ^
    --run-script "%SCRIPT_DIR%src\image_composite_converter.py" -- ^
    "%DEFAULT_FOLDER%" "%DEFAULT_CSV%" %DEFAULT_ITERATIONS% --start %DEFAULT_START% --end %DEFAULT_END% --bootstrap-deps
) else (
  "%PYTHON_EXE%" "%SCRIPT_DIR%src\converter_runtime_bootstrap.py" ^
    --vendor-root "%SCRIPT_DIR%vendor\converter_runtime" ^
    --run-script "%SCRIPT_DIR%src\image_composite_converter.py" -- %*
)

endlocal
