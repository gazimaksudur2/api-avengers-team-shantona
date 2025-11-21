# Complete Setup Guide - CareForAll Platform

This guide will walk you through **every step** from installing dependencies to monitoring and performance testing.

## 📋 Table of Contents

1. [Prerequisites Installation](#1-prerequisites-installation)
2. [Project Setup](#2-project-setup)
3. [Python Dependencies (Local Development)](#3-python-dependencies-local-development)
4. [Docker Environment Setup](#4-docker-environment-setup)
5. [Starting the Platform](#5-starting-the-platform)
6. [Verifying All Services](#6-verifying-all-services)
7. [Testing the APIs](#7-testing-the-apis)
8. [Monitoring Setup (Prometheus)](#8-monitoring-setup-prometheus)
9. [Dashboard Setup (Grafana)](#9-dashboard-setup-grafana)
10. [Distributed Tracing (Jaeger)](#10-distributed-tracing-jaeger)
11. [Performance Testing](#11-performance-testing)
12. [Advanced Monitoring](#12-advanced-monitoring)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Prerequisites Installation

### Windows Setup

#### 1.1 Install Python 3.11+

```powershell
# Download Python from official website
# https://www.python.org/downloads/

# Verify installation
python --version
# Expected: Python 3.11.x or higher

# Verify pip
pip --version
```

#### 1.2 Install Docker Desktop

```powershell
# Download Docker Desktop for Windows
# https://www.docker.com/products/docker-desktop

# After installation, verify
docker --version
# Expected: Docker version 20.10.x or higher

docker-compose --version
# Expected: Docker Compose version 2.x or higher
```

#### 1.3 Install Git

```powershell
# Download Git for Windows
# https://git-scm.com/download/win

# Verify
git --version
```

#### 1.4 Install curl (for testing)

```powershell
# curl comes with Windows 10+
curl --version

# If not available, install via:
# https://curl.se/windows/
```

#### 1.5 Install a JSON viewer (Optional)

```powershell
# Install jq for pretty JSON output
# Download from: https://stedolan.github.io/jq/download/

# Or use PowerShell's ConvertFrom-Json
```

### Linux/Mac Setup

```bash
# Python
sudo apt-get update
sudo apt-get install python3.11 python3-pip -y

# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Git & curl
sudo apt-get install git curl jq -y
```

---

## 2. Project Setup

### 2.1 Clone/Navigate to Project

```bash
# Navigate to project directory
cd D:\DevProjects\HackathonProjects\API_avengers

# Verify structure
dir  # Windows
ls   # Linux/Mac

# You should see:
# - services/
# - api-gateway/
# - observability/
# - docker-compose.yml
# - README.md
```

### 2.2 Make Scripts Executable (Linux/Mac)

```bash
chmod +x test-scenarios/*.sh
chmod +x init-db.sh
```

### 2.3 Configure Environment Variables (Optional)

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your values (optional for demo)
# For demo, defaults work fine
```

---

## 3. Python Dependencies (Optional - Not Required!)

⚠️ **IMPORTANT**: You **DON'T need to install Python dependencies locally!** Everything runs in Docker containers with pre-installed dependencies.

**Skip to Section 4 if you just want to run the platform.**

### 3.1 Local Installation (Optional for IDE Autocomplete)

Only do this if you want IDE autocomplete or plan to run services outside Docker.

#### Windows Users - psycopg2-binary Issue Fix

If you get `pg_config executable not found` error:

**Option 1: Skip psycopg2 (Recommended)**
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install everything EXCEPT database drivers (enough for autocomplete)
pip install fastapi uvicorn sqlalchemy pydantic pydantic-settings pika redis prometheus-client opentelemetry-api opentelemetry-sdk pytest httpx
```

**Option 2: Use Precompiled Wheel**
```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Force binary installation
pip install psycopg2-binary --only-binary :all:
pip install -r requirements.txt --only-binary psycopg2-binary
```

**Option 3: Install PostgreSQL**
1. Download from https://www.postgresql.org/download/windows/
2. Install (includes pg_config)
3. Add `C:\Program Files\PostgreSQL\15\bin` to PATH
4. Try `pip install -r requirements.txt` again

### 3.2 Linux/Mac Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd services/donation-service
pip install -r requirements.txt
cd ../..
```

### 3.3 Verify Installation

```bash
# Check FastAPI
python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"

# Check SQLAlchemy
python -c "import sqlalchemy; print(f'SQLAlchemy: {sqlalchemy.__version__}')"

# Check OpenTelemetry
python -c "import opentelemetry; print('OpenTelemetry: OK')"

# Check Prometheus client
python -c "import prometheus_client; print('Prometheus client: OK')"
```

**Expected Output:**
```
FastAPI: 0.104.1
SQLAlchemy: 2.0.23
OpenTelemetry: OK
Prometheus client: OK
```

---

## 4. Docker Environment Setup

### 4.1 Verify Docker is Running

```powershell
# Check Docker daemon
docker ps

# Expected: Table showing running containers (may be empty)
```

### 4.2 Pull Base Images (Optional - speeds up first build)

```bash
docker pull python:3.11-slim
docker pull nginx:alpine
docker pull postgres:15-alpine
docker pull redis:7-alpine
docker pull rabbitmq:3-management-alpine
docker pull prom/prometheus:latest
docker pull grafana/grafana:latest
docker pull jaegertracing/all-in-one:latest
```

### 4.3 Build Service Images

```bash
# Build all service images (this may take 5-10 minutes)
docker-compose build

# Expected output:
# [+] Building ... donation-service
# [+] Building ... payment-service
# [+] Building ... totals-service
# [+] Building ... notification-service
```

**Troubleshooting Build Issues:**
```bash
# If build fails, try:
docker-compose build --no-cache

# Or build individual service:
docker-compose build donation-service
```

---

## 5. Starting the Platform

### 5.1 Start All Services

```bash
# Start in detached mode (background)
docker-compose up -d

# Expected output:
# [+] Running 13/13
#  ✔ Network api_avengers_backend     Created
#  ✔ Network api_avengers_public      Created
#  ✔ Container postgres               Started
#  ✔ Container redis                  Started
#  ✔ Container rabbitmq               Started
#  ✔ Container donation-service       Started
#  ✔ Container payment-service        Started
#  ✔ Container totals-service         Started
#  ✔ Container notification-service   Started
#  ✔ Container outbox-processor       Started
#  ✔ Container api-gateway            Started
#  ✔ Container prometheus             Started
#  ✔ Container grafana                Started
#  ✔ Container jaeger                 Started
```

### 5.2 Wait for Services to Initialize

```bash
# Wait 30 seconds for all services to be ready
# Windows PowerShell
Start-Sleep -Seconds 30

# Linux/Mac
sleep 30
```

### 5.3 Check Service Status

```bash
# View all containers
docker-compose ps

# Expected: All services should show "running" or "Up"
```

**Expected Output:**
```
NAME                   STATUS              PORTS
api-gateway           Up 30 seconds       0.0.0.0:8000->80/tcp
donation-service      Up 30 seconds       8001/tcp
payment-service       Up 30 seconds       8002/tcp
totals-service        Up 30 seconds       8003/tcp
notification-service  Up 30 seconds       8004/tcp
postgres              Up 30 seconds       0.0.0.0:5432->5432/tcp
redis                 Up 30 seconds       0.0.0.0:6379->6379/tcp
rabbitmq              Up 30 seconds       0.0.0.0:5672->5672/tcp, 0.0.0.0:15672->15672/tcp
prometheus            Up 30 seconds       0.0.0.0:9090->9090/tcp
grafana               Up 30 seconds       0.0.0.0:3000->3000/tcp
jaeger                Up 30 seconds       0.0.0.0:16686->16686/tcp
```

### 5.4 View Logs (Real-time)

```bash
# View all service logs
docker-compose logs -f

# View specific service
docker-compose logs -f donation-service
docker-compose logs -f payment-service

# Press Ctrl+C to exit
```

---

## 6. Verifying All Services

### 6.1 Check API Gateway

```bash
curl http://localhost:8000/health

# Expected:
# HTTP/200 OK
# "healthy"
```

### 6.2 Check Donation Service

```bash
curl http://localhost:8001/health

# Expected (JSON):
{
  "status": "healthy",
  "service": "donation-service",
  "timestamp": "2025-11-21T...",
  "checks": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

### 6.3 Check Payment Service

```bash
curl http://localhost:8002/health

# Expected: Similar to donation service
```

### 6.4 Check Totals Service

```bash
curl http://localhost:8003/health
```

### 6.5 Check Notification Service

```bash
curl http://localhost:8004/health
```

### 6.6 Quick Health Check Script (Windows PowerShell)

```powershell
# Create a health check script
$services = @(
    @{Name="API Gateway"; URL="http://localhost:8000/health"},
    @{Name="Donation Service"; URL="http://localhost:8001/health"},
    @{Name="Payment Service"; URL="http://localhost:8002/health"},
    @{Name="Totals Service"; URL="http://localhost:8003/health"},
    @{Name="Notification Service"; URL="http://localhost:8004/health"}
)

foreach ($service in $services) {
    try {
        $response = Invoke-WebRequest -Uri $service.URL -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ $($service.Name): Healthy" -ForegroundColor Green
        }
    } catch {
        Write-Host "✗ $($service.Name): Unhealthy" -ForegroundColor Red
    }
}
```

### 6.7 Quick Health Check Script (Linux/Mac Bash)

```bash
#!/bin/bash
# Save as check_health.sh

services=(
    "API Gateway:http://localhost:8000/health"
    "Donation Service:http://localhost:8001/health"
    "Payment Service:http://localhost:8002/health"
    "Totals Service:http://localhost:8003/health"
    "Notification Service:http://localhost:8004/health"
)

for service in "${services[@]}"; do
    IFS=':' read -r name url <<< "$service"
    if curl -f -s "$url" > /dev/null; then
        echo "✓ $name: Healthy"
    else
        echo "✗ $name: Unhealthy"
    fi
done
```

---

## 7. Testing the APIs

### 7.1 Create a Test Donation

```bash
# Create donation via API Gateway
curl -X POST http://localhost:8000/api/v1/donations \
  -H "Content-Type: application/json" \
  -d "{
    \"campaign_id\": \"550e8400-e29b-41d4-a716-446655440000\",
    \"donor_email\": \"test@example.com\",
    \"amount\": 100.00,
    \"currency\": \"USD\",
    \"metadata\": {
      \"source\": \"manual_test\"
    }
  }"

# Save the returned donation_id for next steps
```

**Expected Response:**
```json
{
  "id": "a1b2c3d4-...",
  "campaign_id": "550e8400-...",
  "donor_email": "test@example.com",
  "amount": 100.00,
  "currency": "USD",
  "status": "PENDING",
  "payment_intent_id": null,
  "created_at": "2025-11-21T...",
  "updated_at": "2025-11-21T...",
  "version": 1
}
```

### 7.2 Get Donation Details

```bash
# Replace {donation-id} with actual ID from previous step
curl http://localhost:8000/api/v1/donations/{donation-id}
```

### 7.3 Get Donation History

```bash
curl "http://localhost:8000/api/v1/donations/history?donor_email=test@example.com"
```

### 7.4 Create Payment Intent

```bash
# Use donation_id from step 7.1
curl -X POST http://localhost:8000/api/v1/payments/intent \
  -H "Content-Type: application/json" \
  -d "{
    \"donation_id\": \"{donation-id}\",
    \"amount\": 100.00,
    \"currency\": \"USD\",
    \"gateway\": \"stripe\"
  }"

# Save the payment_intent_id
```

**Expected Response:**
```json
{
  "id": "payment-uuid-...",
  "payment_intent_id": "pi_abc123...",
  "donation_id": "donation-uuid",
  "amount": 100.00,
  "currency": "USD",
  "status": "INITIATED",
  "gateway": "stripe",
  "client_secret": "pi_abc123_secret_xxx",
  "created_at": "2025-11-21T..."
}
```

### 7.5 Simulate Payment Webhook (Test Idempotency)

```bash
# Send webhook (first time)
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: test_webhook_123" \
  -d "{
    \"event_type\": \"payment_intent.succeeded\",
    \"payment_intent_id\": \"pi_abc123\",
    \"status\": \"AUTHORIZED\",
    \"timestamp\": \"2025-11-21T10:00:00Z\"
  }"

# Expected: Status "processed"

# Send SAME webhook again (test idempotency)
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: test_webhook_123" \
  -d "{
    \"event_type\": \"payment_intent.succeeded\",
    \"payment_intent_id\": \"pi_abc123\",
    \"status\": \"AUTHORIZED\",
    \"timestamp\": \"2025-11-21T10:00:00Z\"
  }"

# Expected: SAME response (cached) - proves idempotency works!
```

### 7.6 Get Campaign Totals

```bash
# Get cached totals (fast)
curl http://localhost:8000/api/v1/totals/campaigns/550e8400-e29b-41d4-a716-446655440000

# Get real-time totals (accurate but slower)
curl "http://localhost:8000/api/v1/totals/campaigns/550e8400-e29b-41d4-a716-446655440000?realtime=true"
```

### 7.7 Run Complete Demo Flow

```bash
# Windows PowerShell
.\test-scenarios\demo-flow.sh

# Linux/Mac
./test-scenarios/demo-flow.sh
```

This script will:
1. Create a donation
2. Create payment intent
3. Simulate authorization webhook
4. Simulate capture webhook
5. Update donation status
6. Fetch totals
7. Demonstrate idempotency

---

## 8. Monitoring Setup (Prometheus)

### 8.1 Access Prometheus UI

```bash
# Open in browser
http://localhost:9090
```

### 8.2 Verify Targets are Up

1. Navigate to: **Status → Targets**
2. You should see all services in "UP" state:
   - donation-service
   - payment-service
   - totals-service
   - notification-service

**If any target shows "DOWN":**
```bash
# Check service logs
docker-compose logs [service-name]

# Restart service
docker-compose restart [service-name]
```

### 8.3 Test Prometheus Queries

Navigate to: **Graph** tab

#### Query 1: HTTP Request Rate
```promql
rate(http_requests_total[1m])
```
**Expected**: Graph showing request rate per service

#### Query 2: Total Donations Created
```promql
donation_created_total
```
**Expected**: Counter showing total donations

#### Query 3: P95 Latency
```promql
histogram_quantile(0.95, rate(payment_processing_duration_seconds_bucket[5m]))
```
**Expected**: Graph showing 95th percentile latency

#### Query 4: Cache Hit Ratio
```promql
cache_hit_ratio
```
**Expected**: Gauge between 0 and 1 (should be >0.9 after some requests)

#### Query 5: Idempotency Cache Hits
```promql
rate(idempotency_cache_hits_total[1m])
```
**Expected**: Counter showing cache hits

### 8.4 Create Alert Rules (Optional)

Edit `observability/prometheus/prometheus.yml`:

```yaml
rule_files:
  - 'alerts.yml'
```

Create `observability/prometheus/alerts.yml`:

```yaml
groups:
  - name: careforall_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
```

Reload Prometheus:
```bash
docker-compose restart prometheus
```

---

## 9. Dashboard Setup (Grafana)

### 9.1 Access Grafana UI

```bash
# Open in browser
http://localhost:3000

# Login credentials:
Username: admin
Password: admin

# You'll be prompted to change password (optional for demo)
```

### 9.2 Verify Data Source

1. Navigate to: **Configuration → Data Sources**
2. You should see: **Prometheus** (already configured)
3. Click "Test" button
4. Expected: "Data source is working"

**If not working:**
```bash
# Check Prometheus is accessible from Grafana
docker-compose exec grafana curl http://prometheus:9090/api/v1/query?query=up

# Should return JSON with results
```

### 9.3 Import Pre-configured Dashboard

1. Navigate to: **Dashboards → Browse**
2. You should see: **CareForAll System Overview**
3. Click to open

**If dashboard doesn't appear:**
```bash
# Check dashboard file exists
ls observability/grafana/dashboards/system-overview.json

# Restart Grafana
docker-compose restart grafana

# Wait 10 seconds, refresh browser
```

### 9.4 Explore Dashboard Panels

The pre-configured dashboard includes:

#### Panel 1: HTTP Request Rate
- Shows requests per second for all services
- Should increase when you make API calls

#### Panel 2: P95 Latency
- Shows 95th percentile response time
- Gauge visualization (green = good, yellow = warning, red = critical)

#### Panel 3: Donations per Minute
- Stacked area chart by status (PENDING, COMPLETED, FAILED)

#### Panel 4: Cache Hit Ratio
- Gauge showing percentage of cache hits
- Should be >90% after warming up

#### Panel 5: Webhook Processing
- Shows idempotency cache hits vs misses
- Line chart over time

#### Panel 6: Notifications Sent
- Bar chart of notifications by type and status

### 9.5 Generate Traffic to See Metrics

```bash
# Run stress test to generate traffic
.\test-scenarios\stress-test.sh  # Windows
./test-scenarios/stress-test.sh  # Linux/Mac

# Watch the dashboard update in real-time!
```

### 9.6 Create Custom Panel (Optional)

1. Click **Add Panel** button
2. Select **Add a new panel**
3. Enter query: `rate(donation_created_total[1m])`
4. Choose visualization: **Time series**
5. Panel title: "Donation Rate"
6. Click **Apply**

### 9.7 Set Dashboard Refresh Rate

1. Click the refresh icon (top right)
2. Select **5s** or **10s**
3. Dashboard will auto-refresh to show real-time data

---

## 10. Distributed Tracing (Jaeger)

### 10.1 Access Jaeger UI

```bash
# Open in browser
http://localhost:16686
```

### 10.2 View Traces

1. **Service** dropdown: Select `donation-service`
2. **Operation** dropdown: Select `All` or specific operation
3. Click **Find Traces** button

**You should see:**
- List of traces (each request = 1 trace)
- Trace duration
- Number of spans

### 10.3 Analyze a Single Trace

1. Click on any trace to open details
2. You'll see the complete flow:

```
Trace Timeline:
├─ [8ms] API Gateway
│   └─ HTTP POST /api/v1/donations
├─ [45ms] donation-service: create_donation
│   ├─ [12ms] Database: insert donation
│   └─ [8ms] Database: insert outbox_event
├─ [15ms] outbox-processor: process_batch
│   └─ [5ms] RabbitMQ: publish event
└─ [120ms] notification-service: send_notification
    └─ [95ms] SendGrid: send email
```

### 10.4 Search for Specific Trace

**By Operation:**
```
Service: payment-service
Operation: handle_webhook
```

**By Tag:**
```
Tags: donation_id=a1b2c3d4-...
```

**By Duration:**
```
Min Duration: 100ms
Max Duration: 500ms
```

### 10.5 Identify Performance Bottlenecks

1. Sort traces by **Longest First**
2. Click on longest trace
3. Look for spans with longest duration
4. That's your bottleneck!

Example findings:
- Database queries taking >100ms → add indexes
- External API calls timing out → add circuit breaker
- Service-to-service calls slow → check network

### 10.6 View Service Dependencies

1. Click **System Architecture** tab
2. Shows graph of service dependencies
3. Visual representation of microservices communication

### 10.7 Compare Traces

1. Find similar operations (e.g., create_donation)
2. Compare durations
3. Identify why some are slower than others

---

## 11. Performance Testing

### 11.1 Run Built-in Stress Test

```bash
# Windows PowerShell
.\test-scenarios\stress-test.sh

# Linux/Mac
./test-scenarios/stress-test.sh
```

**This test will:**
1. Create 1000 donations with 100 concurrent requests
2. Test idempotency with duplicate webhooks
3. Test out-of-order webhook handling
4. Test invalid state transition rejection
5. Measure cache performance

**Expected Results:**
```
📊 Test Summary
===============
✓ Donation creation under load: 50+ req/s
✓ Idempotency: Duplicate webhooks handled correctly
✓ State machine: Out-of-order webhooks ignored
✓ State machine: Invalid transitions rejected
✓ Cache performance: <50ms average latency

🎉 All tests passed!
```

### 11.2 Manual Load Test with Apache Bench

**Install Apache Bench:**
```bash
# Windows: Download from https://www.apachelounge.com/download/
# Linux: sudo apt-get install apache2-utils
# Mac: brew install httpd (ab comes with it)
```

**Test Donation Creation:**
```bash
# Create a JSON file: donation.json
{
  "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
  "donor_email": "loadtest@example.com",
  "amount": 50.00,
  "currency": "USD"
}

# Run load test: 1000 requests, 100 concurrent
ab -n 1000 -c 100 -p donation.json -T application/json \
  http://localhost:8000/api/v1/donations
```

**Expected Output:**
```
Requests per second:    500.23 [#/sec]
Time per request:       199.908 [ms] (mean)
Time per request:       1.999 [ms] (mean, across all concurrent requests)
Percentage of requests served within a certain time:
  50%    180ms
  95%    250ms
  99%    300ms
```

### 11.3 Test Cache Performance

```bash
# Test totals endpoint (should be cached)
ab -n 1000 -c 50 \
  http://localhost:8000/api/v1/totals/campaigns/550e8400-e29b-41d4-a716-446655440000
```

**Expected:**
- First request: ~200ms (cache miss)
- Subsequent requests: ~10-50ms (cache hit)
- 95% of requests should be <50ms

### 11.4 Monitor During Load Test

**Open 3 browser tabs:**
1. **Grafana**: http://localhost:3000
   - Watch request rate spike
   - Monitor latency
   - Check error rate stays at 0%

2. **Prometheus**: http://localhost:9090
   - Query: `rate(http_requests_total[1m])`
   - Should show spike in traffic

3. **Jaeger**: http://localhost:16686
   - Watch traces accumulate
   - Check for any slow requests

### 11.5 Performance Benchmarks

After running stress tests, verify these metrics:

| Metric | Target | How to Check |
|--------|--------|--------------|
| **Throughput** | >500 req/s per service | Grafana: HTTP Request Rate |
| **P95 Latency** | <100ms (cached) | Grafana: P95 Latency panel |
| **Cache Hit Ratio** | >90% | Grafana: Cache Hit Ratio |
| **Error Rate** | <1% | Prometheus: `rate(http_requests_total{status=~"5.."}[1m])` |
| **Idempotency Hit** | 100% for duplicates | Grafana: Webhook Processing |

### 11.6 Database Performance

```bash
# Check PostgreSQL connections
docker-compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Should be < 60 connections (20 pool × 3 replicas)

# Check slow queries
docker-compose exec postgres psql -U postgres -d donations_db -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"
```

### 11.7 Redis Performance

```bash
# Check Redis stats
docker-compose exec redis redis-cli INFO stats

# Look for:
# - total_commands_processed: Should be high
# - keyspace_hits: Should be >> keyspace_misses
# - hit rate = hits / (hits + misses) * 100%
```

---

## 12. Advanced Monitoring

### 12.1 RabbitMQ Management UI

```bash
# Open in browser
http://localhost:15672

# Login:
Username: guest
Password: guest
```

**What to Check:**
1. **Queues** tab:
   - `totals.queue` - Should have consumers
   - `notifications.queue` - Should have consumers
   - Messages should be processed (not accumulating)

2. **Exchanges** tab:
   - `donations.events` - Should show message rate
   - `payments.events` - Should show message rate

3. **Connections** tab:
   - Should see connections from all services

### 12.2 Check Outbox Processor

```bash
# View outbox processor logs
docker-compose logs -f outbox-processor

# Should see:
# "✓ Published event 123 (DonationCreated)"
# "Processing 100 outbox events..."
```

### 12.3 Database Monitoring

**Check donation records:**
```bash
docker-compose exec postgres psql -U postgres -d donations_db -c "SELECT COUNT(*) FROM donations;"
```

**Check outbox events:**
```bash
docker-compose exec postgres psql -U postgres -d donations_db -c "SELECT COUNT(*) FROM outbox_events WHERE processed_at IS NULL;"

# Should be 0 or very low (events are processed quickly)
```

**Check payment state history:**
```bash
docker-compose exec postgres psql -U postgres -d payments_db -c "SELECT * FROM payment_state_history ORDER BY received_at DESC LIMIT 10;"
```

### 12.4 Custom Prometheus Queries

**Error Rate by Service:**
```promql
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100
```

**Request Duration Histogram:**
```promql
histogram_quantile(0.99, rate(donation_creation_duration_seconds_bucket[5m]))
```

**Service Availability:**
```promql
avg(up{job=~"donation-service|payment-service|totals-service"}) * 100
```

### 12.5 Log Aggregation

**View logs from all services:**
```bash
# All logs
docker-compose logs

# Follow logs (real-time)
docker-compose logs -f

# Filter by service
docker-compose logs donation-service | grep ERROR

# Tail last 100 lines
docker-compose logs --tail=100 payment-service
```

---

## 13. Troubleshooting

### 13.1 Services Won't Start

**Problem**: Containers exit immediately

```bash
# Check logs
docker-compose logs [service-name]

# Common issues:
# 1. Port already in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac

# 2. Database not ready
# Solution: Wait 30 seconds and restart
docker-compose restart donation-service
```

### 13.2 Health Checks Failing

**Problem**: `/health` endpoint returns 503

```bash
# Check if database is ready
docker-compose exec postgres pg_isready

# Check Redis
docker-compose exec redis redis-cli ping

# Restart affected service
docker-compose restart [service-name]
```

### 13.3 No Metrics in Prometheus

**Problem**: Targets show "DOWN"

```bash
# Check if service exposes /metrics
curl http://localhost:8001/metrics

# Check Prometheus config
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# Restart Prometheus
docker-compose restart prometheus
```

### 13.4 No Traces in Jaeger

**Problem**: No traces appear

```bash
# Check if Jaeger is running
curl http://localhost:16686

# Check if services can reach Jaeger
docker-compose exec donation-service ping jaeger

# Check environment variable
docker-compose exec donation-service env | grep OTEL

# Expected: OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

### 13.5 Grafana Dashboard Empty

**Problem**: Panels show "No data"

```bash
# Check data source connection
# Grafana UI → Configuration → Data Sources → Prometheus → Test

# Check if Prometheus has data
curl "http://localhost:9090/api/v1/query?query=up"

# Reload dashboard
# Click refresh icon, select "Last 5 minutes"
```

### 13.6 Slow Performance

**Problem**: Requests taking >1 second

```bash
# Check CPU/Memory usage
docker stats

# If high, scale down replicas temporarily
docker-compose up -d --scale donation-service=1 --scale payment-service=1

# Check database connections
docker-compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# If high, increase pool size in main.py
```

### 13.7 Reset Everything

```bash
# Stop all containers
docker-compose down

# Remove volumes (⚠️ DELETES ALL DATA)
docker-compose down -v

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```

---

## 📊 Quick Reference Card

### Service URLs
```
API Gateway:          http://localhost:8000
Donation Service:     http://localhost:8001
Payment Service:      http://localhost:8002
Totals Service:       http://localhost:8003
Notification Service: http://localhost:8004
Prometheus:           http://localhost:9090
Grafana:              http://localhost:3000 (admin/admin)
Jaeger:               http://localhost:16686
RabbitMQ:             http://localhost:15672 (guest/guest)
```

### Common Commands
```bash
# Start platform
docker-compose up -d

# Stop platform
docker-compose down

# View logs
docker-compose logs -f

# Health check
curl http://localhost:8000/health

# Run demo
./test-scenarios/demo-flow.sh

# Run stress test
./test-scenarios/stress-test.sh

# Restart service
docker-compose restart [service-name]
```

### Key Metrics to Watch
```
1. HTTP Request Rate (Grafana)
2. P95 Latency (Grafana)
3. Cache Hit Ratio (Grafana)
4. Error Rate (Prometheus)
5. Service Availability (Prometheus: up)
```

---

## 🎉 Success Checklist

After following this guide, verify:

- [ ] All 13 containers running (`docker-compose ps`)
- [ ] All health checks passing
- [ ] Created test donation successfully
- [ ] Prometheus showing metrics
- [ ] Grafana dashboard displaying data
- [ ] Jaeger showing traces
- [ ] Stress test passed
- [ ] Cache hit ratio >90%
- [ ] No errors in logs

**If all checked: 🎉 Your platform is fully operational!**

---

## Need Help?

1. Check **Troubleshooting** section above
2. View logs: `docker-compose logs [service-name]`
3. Review `README.md` for architecture details
4. Check `ARCHITECTURE.md` for technical design
5. See `CORNER_CASES_COVERAGE.md` for implementation details

