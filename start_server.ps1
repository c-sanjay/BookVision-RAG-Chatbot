Write-Host "Starting BookVision RAG FastAPI Server..." -ForegroundColor Green
Write-Host ""
& .\env\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

