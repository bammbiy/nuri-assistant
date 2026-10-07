@echo off
rem Nuri Assistant launcher: double-click to start. The window stays open if start-up fails.
rem Saved in cp949 so the Korean message shows correctly in a Korean Windows console.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 src\run_nuri.py %*
) else (
    python src\run_nuri.py %*
)
if errorlevel 1 (
    echo.
    echo 실행 중 오류가 났습니다. 위 메시지와 %USERPROFILE%\.nuri-assistant\error.log 를 확인하세요.
    pause
)
