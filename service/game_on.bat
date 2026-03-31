@echo off
:: Game Mode ON — stops the assistant to free up resources
:: Double-click to run. Will request admin if needed.

net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit
)

echo Stopping Personal Assistant...
net stop PersonalAssistant >nul 2>&1

if %errorLevel% == 0 (
    echo Assistant stopped. Enjoy your game!
) else (
    echo Assistant was not running.
)

timeout /t 2 >nul
