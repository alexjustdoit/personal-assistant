@echo off
:: Game Mode OFF — restarts the assistant after gaming
:: Double-click to run. Will request admin if needed.

net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit
)

echo Starting Personal Assistant...
net start PersonalAssistant >nul 2>&1

if %errorLevel% == 0 (
    echo Assistant is running at http://localhost:8000
) else (
    echo Failed to start. Check that the service is installed.
)

timeout /t 2 >nul
