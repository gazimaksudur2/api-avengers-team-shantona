# PowerShell Script to Display Key Metrics
# Usage: .\scripts\view-metrics.ps1

Write-Host "`n📊 CareForAll Platform Metrics`n" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

function Get-PrometheusMetric {
    param($query)
    try {
        $url = "http://localhost:9090/api/v1/query?query=$query"
        $response = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 5
        if ($response.status -eq "success" -and $response.data.result.Count -gt 0) {
            return $response.data.result[0].value[1]
        }
        return "N/A"
    } catch {
        return "Error"
    }
}

# Fetch metrics
Write-Host "`n🔢 Business Metrics:" -ForegroundColor Yellow

$totalDonations = Get-PrometheusMetric "sum(donation_created_total)"
Write-Host "   Total Donations Created: " -NoNewline
Write-Host $totalDonations -ForegroundColor Green

$totalPayments = Get-PrometheusMetric "sum(payment_processed_total)"
Write-Host "   Total Payments Processed: " -NoNewline
Write-Host $totalPayments -ForegroundColor Green

Write-Host "`n⚡ Performance Metrics:" -ForegroundColor Yellow

$requestRate = Get-PrometheusMetric "sum(rate(http_requests_total[1m]))"
if ($requestRate -ne "N/A" -and $requestRate -ne "Error") {
    $requestRate = [math]::Round([double]$requestRate, 2)
}
Write-Host "   Request Rate (last 1m): " -NoNewline
Write-Host "$requestRate req/s" -ForegroundColor Green

$cacheHitRatio = Get-PrometheusMetric "cache_hit_ratio"
if ($cacheHitRatio -ne "N/A" -and $cacheHitRatio -ne "Error") {
    $cacheHitRatio = [math]::Round([double]$cacheHitRatio * 100, 1)
    Write-Host "   Cache Hit Ratio: " -NoNewline
    Write-Host "$cacheHitRatio%" -ForegroundColor Green
}

Write-Host "`n🏥 Service Health:" -ForegroundColor Yellow

$upServices = Get-PrometheusMetric "count(up==1)"
Write-Host "   Services Up: " -NoNewline
Write-Host $upServices -ForegroundColor Green

Write-Host "`n📈 Error Rate:" -ForegroundColor Yellow

$errorRate = Get-PrometheusMetric "sum(rate(http_requests_total{status=~'5..'}[5m]))"
if ($errorRate -ne "N/A" -and $errorRate -ne "Error") {
    $errorRate = [math]::Round([double]$errorRate, 4)
}
Write-Host "   5xx Errors (last 5m): " -NoNewline
if ($errorRate -eq 0 -or $errorRate -eq "N/A") {
    Write-Host "$errorRate" -ForegroundColor Green
} else {
    Write-Host "$errorRate" -ForegroundColor Red
}

Write-Host "`n💾 Database:" -ForegroundColor Yellow
Write-Host "   Checking connection pool..."

try {
    $result = docker-compose exec -T postgres psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity;" 2>$null
    if ($result) {
        $connections = $result.Trim()
        Write-Host "   Active Connections: " -NoNewline
        Write-Host $connections -ForegroundColor Green
    }
} catch {
    Write-Host "   Unable to query database" -ForegroundColor Yellow
}

Write-Host "`n📬 Message Queue:" -ForegroundColor Yellow

try {
    $queueInfo = Invoke-RestMethod -Uri "http://localhost:15672/api/queues" -Headers @{Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("guest:guest"))} -Method Get -TimeoutSec 5
    
    $totalsQueue = $queueInfo | Where-Object { $_.name -eq "totals.queue" }
    $notifQueue = $queueInfo | Where-Object { $_.name -eq "notifications.queue" }
    
    if ($totalsQueue) {
        Write-Host "   totals.queue messages: " -NoNewline
        Write-Host $totalsQueue.messages -ForegroundColor Green
    }
    
    if ($notifQueue) {
        Write-Host "   notifications.queue messages: " -NoNewline
        Write-Host $notifQueue.messages -ForegroundColor Green
    }
} catch {
    Write-Host "   Unable to fetch queue stats" -ForegroundColor Yellow
}

Write-Host "`n📊 View detailed metrics at:" -ForegroundColor Cyan
Write-Host "   Grafana:    http://localhost:3000" -ForegroundColor White
Write-Host "   Prometheus: http://localhost:9090" -ForegroundColor White
Write-Host ""

