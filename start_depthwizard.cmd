@echo off
setlocal

set "DEPTHWIZARD_ROOT=%~dp0"

echo Starting DepthWizard backend and frontend...
rem Keep the windows open if a service exits so its real error remains visible.
start "DepthWizard Backend" powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%DEPTHWIZARD_ROOT%start_backend.ps1"
start "DepthWizard Frontend" powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%DEPTHWIZARD_ROOT%start_frontend.ps1"

echo Waiting until both local services answer...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%DEPTHWIZARD_ROOT%wait_and_open.ps1"
if errorlevel 1 (
    echo DepthWizard did not become ready. Read the error in the backend or frontend window.
    pause
    exit /b 1
)

endlocal
