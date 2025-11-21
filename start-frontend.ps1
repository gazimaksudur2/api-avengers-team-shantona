# PowerShell script to start the frontend
# Run this script: .\start-frontend.ps1

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "    Starting CareForAll Frontend" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Node.js is installed
Write-Host "[1/4] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "✅ Node.js installed: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js is not installed!" -ForegroundColor Red
    Write-Host "Please install Node.js from https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Check if backend is running
Write-Host "[2/4] Checking backend services..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ Backend is running" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Backend is not running!" -ForegroundColor Yellow
    Write-Host "Starting backend services..." -ForegroundColor Cyan
    cd ..
    docker-compose up -d
    Start-Sleep -Seconds 30
    cd frontend
}
Write-Host ""

# Install dependencies if needed
Write-Host "[3/4] Checking dependencies..." -ForegroundColor Yellow
if (!(Test-Path "node_modules")) {
    Write-Host "📦 Installing dependencies (this may take a few minutes)..." -ForegroundColor Cyan
    npm install
} else {
    Write-Host "✅ Dependencies already installed" -ForegroundColor Green
}
Write-Host ""

# Start development server
Write-Host "[4/4] Starting development server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "✅ Frontend will start at http://localhost:5173" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

npm run dev

