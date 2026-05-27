@echo off
echo ========================================
echo   BookVision RAG - Backend Server
echo ========================================
echo.
echo Starting FastAPI backend on port 8000...
echo Keep this window open while using the application!
echo.
echo Press Ctrl+C to stop the server
echo.
pause
call env\Scripts\activate.bat
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
