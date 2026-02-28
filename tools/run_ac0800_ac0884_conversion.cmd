@echo off
setlocal enabledelayedexpansion

REM Windows CMD helper: installs deps (optional) and runs AC0800..AC0884 conversion.
REM Usage:
REM   tools\run_ac0800_ac0884_conversion.cmd
REM   tools\run_ac0800_ac0884_conversion.cmd --skip-install
REM   tools\run_ac0800_ac0884_conversion.cmd --python "C:\Path\to\python.exe"

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
pushd "%REPO_ROOT%" >nul

set "PYTHON_BIN="
set "SKIP_INSTALL=0"
set "AC0811_DEBUG_DIR=artifacts\converted_symbols\diff_pngs\tmp_ac0811_element_debug"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--skip-install" (
  set "SKIP_INSTALL=1"
  shift
  goto parse_args
)
if /I "%~1"=="--python" (
  if "%~2"=="" (
    echo [ERROR] --python needs a value.
    popd >nul
    exit /b 2
  )
  set "PYTHON_BIN=%~2"
  shift
  shift
  goto parse_args
)
echo [ERROR] Unknown argument: %~1
echo [INFO] Supported: --skip-install, --python "C:\Path\python.exe"
popd >nul
exit /b 2

:args_done
if "%PYTHON_BIN%"=="" (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    py -3 -c "import sys" >nul 2>nul
    if %ERRORLEVEL%==0 (
      set "PYTHON_BIN=py -3"
    ) else (
      set "PYTHON_BIN=python"
    )
  ) else (
    set "PYTHON_BIN=python"
  )
) else (
  if exist "%PYTHON_BIN%" (
    set "PYTHON_BIN=\"%PYTHON_BIN%\""
  )
)

echo [INFO] Using Python launcher: %PYTHON_BIN%

if "%SKIP_INSTALL%"=="0" (
  echo [INFO] Installing/updating required packages...
  call %PYTHON_BIN% -m pip install --upgrade pip
  if not %ERRORLEVEL%==0 (
    echo [ERROR] Failed to upgrade pip.
    popd >nul
    exit /b %ERRORLEVEL%
  )

  call %PYTHON_BIN% -m pip install numpy opencv-python-headless pymupdf
  if not %ERRORLEVEL%==0 (
    echo [ERROR] Failed to install one or more dependencies.
    popd >nul
    exit /b %ERRORLEVEL%
  )
)

echo [INFO] Running conversion AC0800..AC0884
call %PYTHON_BIN% src\image_composite_converter.py artifacts\images_to_convert artifacts\images_to_convert\nonexistent.csv 8 --start AC0800 --end AC0884 --debug-ac0811-dir "%AC0811_DEBUG_DIR%"
set "CONVERT_EXIT=%ERRORLEVEL%"

if not "%CONVERT_EXIT%"=="0" (
  echo [WARN] Direct conversion failed with exit code %CONVERT_EXIT%.
  echo [INFO] Writing structured attempt logs via helper script...
)

call %PYTHON_BIN% tools\attempt_convert_ac_range.py --start AC0800 --end AC0884 --iterations 8
set "HELPER_EXIT=%ERRORLEVEL%"

if not "%HELPER_EXIT%"=="0" (
  echo [ERROR] Helper script failed with exit code %HELPER_EXIT%.
  popd >nul
  exit /b %HELPER_EXIT%
)

echo [INFO] Done. Check:
echo   - artifacts\converted_symbols\AC0800_AC0884_attempt_report.json
echo   - artifacts\converted_symbols\AC0800_AC0884_attempt_log.md
echo   - %AC0811_DEBUG_DIR%\AC0811_L\round_XX_full_diff.png
echo   - %AC0811_DEBUG_DIR%\AC0811_L\round_XX_circle_diff.png
echo   - %AC0811_DEBUG_DIR%\AC0811_L\round_XX_stem_diff.png

popd >nul
exit /b %CONVERT_EXIT%
