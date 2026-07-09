@echo off
title AXIOM AI Operating System — Stop Server
color 0C

echo =====================================================================
echo                  AXIOM COGNITIVE AI OPERATING SYSTEM
echo                         Stopping Server...
echo =====================================================================
echo.

echo Searching for processes on port 8000...
powershell -Command "$conns = netstat -aon | Select-String ':8000.*LISTENING'; if ($conns) { $conns | ForEach-Object { $proc_pid = ($_ -split '\s+')[-1]; taskkill /PID $proc_pid /F } }"

echo.
echo AXIOM server stopped successfully.
echo =====================================================================
pause
