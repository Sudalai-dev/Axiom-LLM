@echo off
title AXIOM AI Operating System Runner
color 0B

REM This script lives inside axiom/, which is now the project root.
REM Stay here for imports/uvicorn; git operations cd to the true repo root
REM (one level up) so .github/ and other outer-root files are included too.
cd /d "%~dp0"

echo =====================================================================
echo                     AXIOM COGNITIVE AI OPERATING SYSTEM
echo =====================================================================
echo.
echo  [SYSTEM SERVICES INFO]
echo  - Frontend Web Console: http://127.0.0.1:8000/static/index.html
echo  - Backend API Gateway:  http://127.0.0.1:8000/api/v1
echo  - API Documentation:    http://127.0.0.1:8000/api/docs
echo  - Health Check:         http://127.0.0.1:8000/health
echo.
echo  [SECURED LOCAL SYSTEM ACCESS]
echo  - Seeded Username: admin
echo  - Seeded Password: admin123
echo.
echo =====================================================================
echo.
echo Select an option:
echo  [1] Run AXIOM Platform Locally
echo  [2] Run AXIOM Platform Locally and Push Changes to Git
echo  [3] Push Changes to Git Only
echo  [4] Exit
echo.
set /p opt="Enter your choice (1-4): "

if "%opt%"=="1" goto run_platform
if "%opt%"=="2" goto run_and_push
if "%opt%"=="3" goto push_git
if "%opt%"=="4" goto end
echo Invalid option. Please try again.
pause
goto end

:run_platform
echo.
echo Starting local Uvicorn API server...
echo Starting browser in 3 seconds...
start "" http://127.0.0.1:8000/static/index.html
python -m uvicorn api.gateway:create_gateway_app --factory --host 127.0.0.1 --port 8000 --reload
goto end

:run_and_push
echo.
echo Staging and pushing changes to Git...
pushd "%~dp0\.."
git add .
git commit -m "Auto-commit: Updates to AXIOM Platform"
git push
popd
echo.
echo Starting local Uvicorn API server...
start "" http://127.0.0.1:8000/static/index.html
python -m uvicorn api.gateway:create_gateway_app --factory --host 127.0.0.1 --port 8000 --reload
goto end

:push_git
echo.
echo Staging and pushing changes to Git...
pushd "%~dp0\.."
git add .
set /p msg="Enter commit message: "
git commit -m "%msg%"
git push
popd
echo Done.
pause
goto end

:end
