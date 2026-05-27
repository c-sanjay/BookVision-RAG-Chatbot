@echo off
echo Checking if backend server is running...
echo.

curl -s http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Backend server is running on port 8000!
    echo.
    echo You can access:
    echo   - Health check: http://127.0.0.1:8000/health
    echo   - API docs: http://127.0.0.1:8000/docs
) else (
    echo [ERROR] Backend server is NOT running!
    echo.
    echo Please start the backend server first:
    echo   1. Run: start_backend.bat
    echo   2. Wait for "Application startup complete"
    echo   3. Then start the frontend: start_frontend.bat
)

echo.
pause
