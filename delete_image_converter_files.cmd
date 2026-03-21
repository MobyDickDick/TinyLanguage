@echo off
setlocal EnableExtensions

rem Deletes repository files that belong to the image converter tooling.
rem Run from the repository root. Directories are removed recursively.

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

set "TARGET_COUNT=0"

call :delete_file "src\image_composite_converter.py"
call :delete_file "tests\test_image_composite_converter.py"
call :delete_file "tools\optimize_jpeg_roundtrip_quality.py"
call :delete_file "tools\generate_badge_comparison_set.py"
call :delete_file "docs\jpeg_to_svg_umbauplan.md"
call :delete_dir  "vendor\converter_runtime"

popd >nul

echo.
echo Image converter cleanup complete.
exit /b 0

:delete_file
set /a TARGET_COUNT+=1
if exist %~1 (
    del /f /q %~1
    if exist %~1 (
        echo [WARN] Could not delete file: %~1
    ) else (
        echo [OK] Deleted file: %~1
    )
) else (
    echo [SKIP] File not found: %~1
)
exit /b 0

:delete_dir
set /a TARGET_COUNT+=1
if exist %~1 (
    rmdir /s /q %~1
    if exist %~1 (
        echo [WARN] Could not delete directory: %~1
    ) else (
        echo [OK] Deleted directory: %~1
    )
) else (
    echo [SKIP] Directory not found: %~1
)
exit /b 0
