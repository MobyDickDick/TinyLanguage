@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

"%PYTHON_EXE%" "%SCRIPT_DIR%src\converter_runtime_bootstrap.py" ^
  --vendor-root "%SCRIPT_DIR%vendor\converter_runtime" ^
  --run-script "%SCRIPT_DIR%src\image_composite_converter.py" -- %*

endlocal
