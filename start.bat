@echo off
title AXIOM AI Operating System Runner
color 0B

echo =====================================================================
echo                     AXIOM COGNITIVE AI OPERATING SYSTEM
echo =====================================================================
echo.
echo  [SYSTEM SERVICES INFO]
echo  - Frontend Web Console: http://127.0.0.1:8000/
echo  - Backend API Gateway:  http://127.0.0.1:8000/api/v1
echo.
echo  [SECURED LOCAL SYSTEM ACCESS]
echo  - Seeded Username: admin
echo  - Seeded Password: admin123
echo.
echo =====================================================================
echo  Starting local Uvicorn API server and launching browser...
echo =====================================================================
echo.

:: Launch default web browser pointing to the console URL
start http://127.0.0.1:8000/

:: Start the FastAPI / Uvicorn server process
py -m uvicorn axiom.backend.main:app --host 127.0.0.1 --port 8000

pause
