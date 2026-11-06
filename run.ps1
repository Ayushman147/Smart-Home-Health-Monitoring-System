# WardZero Windows Quickstart Script
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Starting WardZero Healthcare Monitoring Demo" -ForegroundColor Cyan
Write-Host "============================================="

if (-Not (Test-Path "ml\model.pkl")) {
    Write-Host "[*] Training initial Scikit-Learn model on synthetic data..." -ForegroundColor Yellow
    python ml/train.py
}

Write-Host "[*] Launching WardZero Backend and Simulator..." -ForegroundColor Green
Start-Process -FilePath "uvicorn" -ArgumentList "backend.main:app --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 2
Start-Process -FilePath "python" -ArgumentList "simulator/simulator.py"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " WardZero is live! Open your web browser at:" -ForegroundColor White
Write-Host " -> http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

