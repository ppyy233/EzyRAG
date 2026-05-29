# Ezy-RAG V1.0.0 - One-Click Start
# Usage: Right-click -> Run with PowerShell, or: .\start.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON = Join-Path $ROOT ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "============================================================"
Write-Host "  Ezy-RAG V1.0.0 - One-Click Start"
Write-Host "============================================================"
Write-Host ""

if (-not (Test-Path $PYTHON)) {
    Write-Host "[ERROR] Python venv not found. Run: uv sync" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$distPath = Join-Path $ROOT "frontend\dist\index.html"
if (-not (Test-Path $distPath)) {
    Write-Host "[INFO] Building frontend..." -ForegroundColor Yellow
    Push-Location (Join-Path $ROOT "frontend")
    & npm install
    & npm run build
    Pop-Location
}

function Test-Port($port) {
    $result = netstat -ano | Select-String ":$port\s.*LISTENING"
    return $null -ne $result
}

Write-Host "[1/3] ChromaDB (port 9898)..." -NoNewline
if (Test-Port 9898) {
    Write-Host " already running" -ForegroundColor Green
} else {
    Start-Process -FilePath $PYTHON -ArgumentList "-m", "servers.chroma" -WorkingDirectory $ROOT -WindowStyle Hidden
    Start-Sleep -Seconds 5
    if (Test-Port 9898) {
        Write-Host " started" -ForegroundColor Green
    } else {
        Write-Host " FAILED" -ForegroundColor Red
    }
}

Write-Host "[2/3] API Server (port 9767)..." -NoNewline
if (Test-Port 9767) {
    Write-Host " already running" -ForegroundColor Green
} else {
    Start-Process -FilePath $PYTHON -ArgumentList "-m", "servers.api" -WorkingDirectory $ROOT -WindowStyle Hidden
    Start-Sleep -Seconds 5
    if (Test-Port 9767) {
        Write-Host " started" -ForegroundColor Green
    } else {
        Write-Host " FAILED" -ForegroundColor Red
    }
}

Write-Host "[3/3] Opening browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:9767/"

Write-Host ""
Write-Host "============================================================"
Write-Host "  Done!" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend: http://127.0.0.1:9767/"
Write-Host "  API Docs: http://127.0.0.1:9767/docs"
Write-Host ""
Write-Host "  Close this window - services keep running."
Write-Host "============================================================"
Read-Host "Press Enter to exit"
