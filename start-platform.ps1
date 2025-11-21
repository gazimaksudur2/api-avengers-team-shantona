# PowerShell script to start CareForAll Platform
# Run this script: .\start-platform.ps1

Write-Host "🚀 Starting CareForAll Platform..." -ForegroundColor Green
Write-Host ""

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "❌ Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Docker is running" -ForegroundColor Green
Write-Host ""

# Check for mode parameter
param(
    [string]$Mode = "default"
)

# Start services based on mode
switch ($Mode.ToLower()) {
    "dev" {
        Write-Host "📦 Starting in DEVELOPMENT mode..." -ForegroundColor Cyan
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    }
    "prod" {
        Write-Host "🏭 Starting in PRODUCTION mode..." -ForegroundColor Cyan
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    }
    default {
        Write-Host "📦 Starting in DEFAULT mode..." -ForegroundColor Cyan
        docker-compose up -d
    }
}

Write-Host ""
Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

Write-Host ""
Write-Host "🏥 Checking service health..." -ForegroundColor Cyan

$services = @(
    @{Name = "API Gateway"; Url = "http://localhost:8000/health"},
    @{Name = "Donation Service"; Url = "http://localhost:8001/health"},
    @{Name = "Payment Service"; Url = "http://localhost:8002/health"},
    @{Name = "Totals Service"; Url = "http://localhost:8003/health"},
    @{Name = "Notification Service"; Url = "http://localhost:8004/health"},
    @{Name = "Campaign Service"; Url = "http://localhost:8005/health"},
    @{Name = "Bank Service"; Url = "http://localhost:8006/health"},
    @{Name = "Admin Service"; Url = "http://localhost:8007/health"}
)

foreach ($service in $services) {
    Write-Host -NoNewline "  $($service.Name): "
    try {
        $response = Invoke-WebRequest -Uri $service.Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Healthy" -ForegroundColor Green
        } else {
            Write-Host "❌ Unhealthy" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ Unhealthy" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Platform is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "📍 Access Points:" -ForegroundColor Cyan
Write-Host "   API Gateway:  http://localhost:8000" -ForegroundColor White
Write-Host "   Grafana:      http://localhost:3000 (admin/admin)" -ForegroundColor White
Write-Host "   Prometheus:   http://localhost:9090" -ForegroundColor White
Write-Host "   Jaeger:       http://localhost:16686" -ForegroundColor White
Write-Host "   RabbitMQ:     http://localhost:15672 (guest/guest)" -ForegroundColor White
Write-Host ""

Write-Host "📊 View logs:" -ForegroundColor Cyan
Write-Host "   docker-compose logs -f" -ForegroundColor White
Write-Host ""

Write-Host "🛑 Stop platform:" -ForegroundColor Cyan
Write-Host "   docker-compose down" -ForegroundColor White
Write-Host ""

Write-Host "📚 Documentation:" -ForegroundColor Cyan
Write-Host "   See DOCKER_GUIDE.md for complete guide" -ForegroundColor White
Write-Host ""

