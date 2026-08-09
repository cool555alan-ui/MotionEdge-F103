@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
set "PYTHONPATH=%PROJECT_ROOT%\host"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%PROJECT_ROOT%"
title MotionEdge Phase 9 Hardware Validation

echo Phase 9 hardware validation - ASCII console
echo Port: COM4, 115200 8N1, Servo: SG90
echo Press Ctrl+C at any time to abort. The validator sends ESTOP on exit.
echo.

python ".\host\phase9_hardware_validate.py" ^
  --port COM4 ^
  --baud 115200 ^
  --duration 600 ^
  --servo-model SG90 ^
  --output ".\artifacts\phase09"

set "VALIDATION_EXIT=%ERRORLEVEL%"
echo.
echo Validation exit code: %VALIDATION_EXIT%
pause
exit /b %VALIDATION_EXIT%
