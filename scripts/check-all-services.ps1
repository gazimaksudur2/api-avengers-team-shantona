# PowerShell Script to Check All Services Health
# Usage: .\scripts\check-all-services.ps1

Write-Host "`n🔍 CareForAll Platform Health Check`n" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Cyan

$services = @(
    @{Name="API Gateway"; URL="http://localhost:8000/health"},
    @{Name="Donation Service"; URL="http://localhost:8001/health"},
    @{Name="Payment Service"; URL="http://localhost:8002/health"},
    @{Name="Totals Service"; URL="http://localhost:8003/health"},
    @{Name="Notification Service"; URL="http://localhost:8004/health"},
    @{Name="Prometheus"; URL="http://localhost:9090/-/healthy"},
    @{Name="Grafana"; URL="http://localhost:3000/api/health"},
    @{Name="Jaeger"; URL="http://localhost:16686/"},
    @{Name="RabbitMQ"; URL="http://localhost:15672/"}
)

$allHealthy = $true

foreach ($service in $services) {
    try {
        $response = Invoke-WebRequest -Uri $service.URL -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ $($service.Name): " -NoNewline -ForegroundColor Green
            Write-Host "Healthy" -ForegroundColor Green
        } else {
            Write-Host "⚠ $($service.Name): " -NoNewline -ForegroundColor Yellow
            Write-Host "HTTP $($response.StatusCode)" -ForegroundColor Yellow
            $allHealthy = $false
        }
    } catch {
        Write-Host "✗ $($service.Name): " -NoNewline -ForegroundColor Red
        Write-Host "Unreachable" -ForegroundColor Red
        $allHealthy = $false
    }
}

Write-Host "`n" -NoNewline

if ($allHealthy) {
    Write-Host "🎉 All services are healthy!" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some services are unhealthy. Check logs with:" -ForegroundColor Yellow
    Write-Host "   docker-compose logs [service-name]" -ForegroundColor Yellow
}

Write-Host "`n📊 Quick Links:" -ForegroundColor Cyan
Write-Host "   Grafana:    http://localhost:3000 (admin/admin)" -ForegroundColor White
Write-Host "   Prometheus: http://localhost:9090" -ForegroundColor White
Write-Host "   Jaeger:     http://localhost:16686" -ForegroundColor White
Write-Host "   RabbitMQ:   http://localhost:15672 (guest/guest)" -ForegroundColor White
Write-Host ""

