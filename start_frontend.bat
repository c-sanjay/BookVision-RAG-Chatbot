@echo off
echo ========================================
echo   BookVision RAG - Frontend Server
echo ========================================
echo.
echo Starting Streamlit frontend...
echo.
echo IMPORTANT: Make sure the backend server is running first!
echo Backend should be at: http://127.0.0.1:8000
echo.
echo Frontend will open at: http://localhost:8501
echo.
pause
call env\Scripts\activate.bat
streamlit run ui/app.py
pause
