@echo off
title E203+Dilithium+PUF board bring-up
set TASKKILL=C:\Windows\System32\taskkill.exe
set PY=D:\python1\python.exe

echo ============================================================
echo   E203 + Dilithium + PUF  board one-click bring-up
echo   Checklist: board POWERED ON, both USB cables plugged in,
echo   and no serial tool (sscom/putty/serial_term) is open.
echo ============================================================
pause

echo.
echo [0/3] Kill stale openocd/gdb processes...
%TASKKILL% /F /IM openocd.exe >nul 2>&1
%TASKKILL% /F /IM riscv-nuclei-elf-gdb.exe >nul 2>&1

echo [1/3] Start openocd (separate window, keep it open)...
start "openocd-server" /D "D:\FPGA\NucleiStudio\NucleiStudio\toolchain\openocd\bin" cmd /k "openocd.exe -f ../scripts/board/nuclei-demosoc-v2.cfg"

echo [2/3] Load firmware and run self-check...
%PY% D:\FPGA\Dilithium-master\board_bringup.py
if errorlevel 1 (
    echo.
    echo *** SELF-CHECK FAILED.                                   ***
    echo *** Stuck at openocd  : unplug/replug the DEBUGGER USB.  ***
    echo *** PUF timeout       : unplug the PUF board's 3V3 wire  ***
    echo *** for 10 seconds, plug back firmly, then re-run this.  ***
    pause
    exit /b 1
)

echo [3/3] Launch GUI...
start "PUF-GUI" /D "D:\FPGA\puf_pqc_demo_gui" cmd /k "%PY% main.py"

echo.
echo DONE. A console window titled PUF-GUI just opened, and the GUI
echo window should appear on top of it within a few seconds.
echo If the PUF-GUI console shows an error, copy it and ask me.
pause
