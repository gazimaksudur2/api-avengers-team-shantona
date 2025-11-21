# PowerShell Script for Quick API Testing
# Usage: .\scripts\quick-test.ps1

Write-Host "`n🧪 Quick API Test`n" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$baseUrl = "http://localhost:8000"
$campaignId = "550e8400-e29b-41d4-a716-446655440000"

# Test 1: Create Donation
Write-Host "`n1️⃣  Creating test donation..." -ForegroundColor Yellow

$donationData = @{
    campaign_id = $campaignId
    donor_email = "quicktest@example.com"
    amount = 99.99
    currency = "USD"
    metadata = @{
        source = "quick_test_script"
        timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    }
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/v1/donations" `
        -Method Post `
        -Body $donationData `
        -ContentType "application/json" `
        -TimeoutSec 10
    
    Write-Host "   ✓ Donation created successfully!" -ForegroundColor Green
    Write-Host "   Donation ID: " -NoNewline
    Write-Host $response.id -ForegroundColor Cyan
    Write-Host "   Amount: " -NoNewline
    Write-Host "$($response.amount) $($response.currency)" -ForegroundColor Cyan
    Write-Host "   Status: " -NoNewline
    Write-Host $response.status -ForegroundColor Cyan
    
    $donationId = $response.id
} catch {
    Write-Host "   ✗ Failed to create donation" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Get Donation
Write-Host "`n2️⃣  Retrieving donation..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/v1/donations/$donationId" `
        -Method Get `
        -TimeoutSec 10
    
    Write-Host "   ✓ Donation retrieved successfully!" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Failed to retrieve donation" -ForegroundColor Red
}

# Test 3: Create Payment Intent
Write-Host "`n3️⃣  Creating payment intent..." -ForegroundColor Yellow

$paymentData = @{
    donation_id = $donationId
    amount = 99.99
    currency = "USD"
    gateway = "stripe"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/v1/payments/intent" `
        -Method Post `
        -Body $paymentData `
        -ContentType "application/json" `
        -TimeoutSec 10
    
    Write-Host "   ✓ Payment intent created!" -ForegroundColor Green
    Write-Host "   Payment Intent ID: " -NoNewline
    Write-Host $response.payment_intent_id -ForegroundColor Cyan
    
    $paymentIntentId = $response.payment_intent_id
} catch {
    Write-Host "   ✗ Failed to create payment intent" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 4: Simulate Webhook (Test Idempotency)
Write-Host "`n4️⃣  Testing webhook idempotency..." -ForegroundColor Yellow

$webhookData = @{
    event_type = "payment_intent.succeeded"
    payment_intent_id = $paymentIntentId
    status = "AUTHORIZED"
    timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
} | ConvertTo-Json

$idempotencyKey = "quicktest_" + (Get-Date -Format "yyyyMMddHHmmss")

try {
    # First webhook
    $response1 = Invoke-RestMethod -Uri "$baseUrl/api/v1/payments/webhook" `
        -Method Post `
        -Body $webhookData `
        -ContentType "application/json" `
        -Headers @{"X-Idempotency-Key" = $idempotencyKey} `
        -TimeoutSec 10
    
    Write-Host "   ✓ First webhook processed" -ForegroundColor Green
    
    # Duplicate webhook (same idempotency key)
    Start-Sleep -Milliseconds 500
    $response2 = Invoke-RestMethod -Uri "$baseUrl/api/v1/payments/webhook" `
        -Method Post `
        -Body $webhookData `
        -ContentType "application/json" `
        -Headers @{"X-Idempotency-Key" = $idempotencyKey} `
        -TimeoutSec 10
    
    # Compare responses
    $response1Json = $response1 | ConvertTo-Json -Compress
    $response2Json = $response2 | ConvertTo-Json -Compress
    
    if ($response1Json -eq $response2Json) {
        Write-Host "   ✓ Duplicate webhook returned cached response!" -ForegroundColor Green
        Write-Host "   ✓ Idempotency working correctly!" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ Responses differ (may be expected)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ✗ Webhook test failed" -ForegroundColor Red
}

# Test 5: Get Campaign Totals
Write-Host "`n5️⃣  Getting campaign totals..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/v1/totals/campaigns/$campaignId" `
        -Method Get `
        -TimeoutSec 10
    
    Write-Host "   ✓ Campaign totals retrieved!" -ForegroundColor Green
    Write-Host "   Total Donations: " -NoNewline
    Write-Host $response.total_donations -ForegroundColor Cyan
    Write-Host "   Total Amount: " -NoNewline
    Write-Host $response.total_amount -ForegroundColor Cyan
    Write-Host "   Data Source: " -NoNewline
    Write-Host $response.data_source -ForegroundColor Cyan
} catch {
    Write-Host "   ✗ Failed to get totals" -ForegroundColor Red
}

# Test 6: Get Donation History
Write-Host "`n6️⃣  Getting donation history..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/v1/donations/history?donor_email=quicktest@example.com" `
        -Method Get `
        -TimeoutSec 10
    
    Write-Host "   ✓ History retrieved!" -ForegroundColor Green
    Write-Host "   Total donations for this donor: " -NoNewline
    Write-Host $response.Count -ForegroundColor Cyan
} catch {
    Write-Host "   ✗ Failed to get history" -ForegroundColor Red
}

# Summary
Write-Host "`n" -NoNewline
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "🎉 Quick test completed!" -ForegroundColor Green
Write-Host "`n💡 Next steps:" -ForegroundColor Cyan
Write-Host "   - View traces in Jaeger:     http://localhost:16686" -ForegroundColor White
Write-Host "   - View metrics in Grafana:   http://localhost:3000" -ForegroundColor White
Write-Host "   - Run full demo:             .\test-scenarios\demo-flow.sh" -ForegroundColor White
Write-Host "   - Run stress test:           .\test-scenarios\stress-test.sh" -ForegroundColor White
Write-Host ""

