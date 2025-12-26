@echo off
echo Starting BookVision RAG FastAPI Server...
echo.
call env\Scripts\activate.bat
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause

