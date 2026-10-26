Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    EchoMap Spatial Awareness Suite     " -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan

# 1. Start Python FastAPI backend in background
Write-Host "[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000" -PassThru

# 2. Start Next.js frontend dev server
Write-Host "[2/2] Starting Next.js Dev Server on http://localhost:3000..." -ForegroundColor Yellow
Start-Process "http://localhost:3000"
npm run dev
