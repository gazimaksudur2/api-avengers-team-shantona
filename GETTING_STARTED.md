# Getting Started with CareForAll Platform

This guide will walk you through running and testing the complete fundraising platform.

## Prerequisites

Before you begin, ensure you have:

- **Docker** (version 20.10+)
- **Docker Compose** (version 2.0+)
- **curl** or **Postman** for API testing
- **Git**

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd API_avengers

# Make test scripts executable
chmod +x test-scenarios/*.sh
```

## Step 2: Start the Platform

```bash
# Start all services
docker-compose up -d

# This will start:
# - API Gateway (Nginx)
# - 3 replicas of Donation Service
# - 3 replicas of Payment Service
# - 2 replicas of Totals Service
# - 2 replicas of Notification Service
# - PostgreSQL
# - Redis
# - RabbitMQ
# - Prometheus
# - Grafana
# - Jaeger

# Wait for services to be ready (~30 seconds)
sleep 30

# Check status
docker-compose ps
```

## Step 3: Verify Services are Healthy

```bash
# Check API Gateway
curl http://localhost:8000/health
# Expected: HTTP 200 with "healthy" status

# Check individual services
curl http://localhost:8001/health  # Donation Service
curl http://localhost:8002/health  # Payment Service
curl http://localhost:8003/health  # Totals Service
curl http://localhost:8004/health  # Notification Service
```

## Step 4: Run the Demo Flow

```bash
# Run the complete donation lifecycle demo
./test-scenarios/demo-flow.sh

# This will:
# 1. Create a donation
# 2. Create a payment intent
# 3. Simulate payment authorization webhook
# 4. Simulate payment capture webhook
# 5. Update donation status
# 6. Fetch updated totals
# 7. Retrieve donation history
# 8. Demonstrate idempotency
```

## Step 5: Explore Observability Dashboards

### Grafana (Metrics & Dashboards)

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to Dashboards → CareForAll → System Overview
4. Observe real-time metrics:
   - HTTP request rate
   - P95 latency
   - Donations per minute
   - Cache hit ratio
   - Webhook processing (idempotency)

### Jaeger (Distributed Tracing)

1. Open http://localhost:16686
2. Select service: `donation-service`
3. Click "Find Traces"
4. Click on any trace to see the complete flow:
   ```
   API Gateway → Donation Service → Database → Outbox → RabbitMQ → Notification Service
   ```

### Prometheus (Raw Metrics)

1. Open http://localhost:9090
2. Try these queries:
   ```promql
   # Request rate
   rate(http_requests_total[1m])
   
   # P95 latency
   histogram_quantile(0.95, rate(payment_processing_duration_seconds_bucket[5m]))
   
   # Cache hit ratio
   cache_hit_ratio
   
   # Idempotency cache hits
   rate(idempotency_cache_hits_total[1m])
   ```

### RabbitMQ (Message Broker)

1. Open http://localhost:15672
2. Login with `guest` / `guest`
3. Navigate to Queues to see:
   - `totals.queue`
   - `notifications.queue`
   - Event flow between services

## Step 6: Manual API Testing

### Create a Donation

```bash
curl -X POST http://localhost:8000/api/v1/donations \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
    "donor_email": "your.email@example.com",
    "amount": 50.00,
    "currency": "USD",
    "metadata": {
      "source": "website",
      "campaign_name": "Help Children"
    }
  }'

# Save the donation ID from the response
```

### Get Donation Details

```bash
curl http://localhost:8000/api/v1/donations/{donation-id}
```

### Get Donor History

```bash
curl "http://localhost:8000/api/v1/donations/history?donor_email=your.email@example.com"
```

### Create Payment Intent

```bash
curl -X POST http://localhost:8000/api/v1/payments/intent \
  -H "Content-Type: application/json" \
  -d '{
    "donation_id": "{donation-id}",
    "amount": 50.00,
    "currency": "USD",
    "gateway": "stripe"
  }'

# Save the payment_intent_id from the response
```

### Simulate Payment Webhook (with Idempotency)

```bash
# First webhook
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: unique_key_123" \
  -d '{
    "event_type": "payment_intent.succeeded",
    "payment_intent_id": "{payment-intent-id}",
    "status": "AUTHORIZED",
    "timestamp": "2025-11-21T10:00:00Z"
  }'

# Send same webhook again (with same idempotency key)
# Should return identical cached response
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: unique_key_123" \
  -d '{
    "event_type": "payment_intent.succeeded",
    "payment_intent_id": "{payment-intent-id}",
    "status": "AUTHORIZED",
    "timestamp": "2025-11-21T10:00:00Z"
  }'
```

### Get Campaign Totals

```bash
# Cached (fast)
curl http://localhost:8000/api/v1/totals/campaigns/550e8400-e29b-41d4-a716-446655440000

# Real-time (accurate but slower)
curl "http://localhost:8000/api/v1/totals/campaigns/550e8400-e29b-41d4-a716-446655440000?realtime=true"
```

## Step 7: Run Stress Tests

```bash
# Run comprehensive stress tests
./test-scenarios/stress-test.sh

# This will:
# 1. Create 1000 donations with 100 concurrent requests
# 2. Test idempotency with duplicate webhooks
# 3. Test out-of-order webhook handling
# 4. Test invalid state transition rejection
# 5. Measure cache performance

# Watch metrics in Grafana during the test
```

## Step 8: Test Fault Tolerance

### Test Outbox Pattern (Reliability)

```bash
# Stop RabbitMQ to simulate message broker failure
docker-compose stop rabbitmq

# Create donations - they should still work
curl -X POST http://localhost:8000/api/v1/donations ...

# Events are queued in outbox table

# Restart RabbitMQ
docker-compose start rabbitmq

# Watch outbox processor publish queued events
docker-compose logs -f outbox-processor
```

### Test Service Failure Recovery

```bash
# Stop payment service
docker-compose stop payment-service

# Payment webhooks will fail (expected)

# Restart payment service
docker-compose start payment-service

# System recovers automatically
```

### Test Cache Invalidation

```bash
# Get totals (should be cached)
curl http://localhost:8000/api/v1/totals/campaigns/550e8400-e29b-41d4-a716-446655440000

# Complete a donation (triggers cache invalidation)
# ... (create and complete donation)

# Get totals again (cache invalidated, recalculated)
curl http://localhost:8000/api/v1/totals/campaigns/550e8400-e29b-41d4-a716-446655440000
```

## Step 9: Run Unit Tests

```bash
# Test Donation Service (including outbox pattern)
docker-compose run donation-service pytest test_main.py -v

# Test Payment Service (including idempotency tests)
docker-compose run payment-service pytest test_main.py -v

# Run specific test
docker-compose run payment-service pytest test_main.py::test_webhook_idempotency_same_key -v
```

## Step 10: View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f donation-service
docker-compose logs -f payment-service
docker-compose logs -f outbox-processor

# Filter for errors
docker-compose logs | grep ERROR
```

## Common Scenarios

### Scenario 1: Test Idempotency

```bash
# Create payment
PAYMENT_ID="pi_test_123"

# Send webhook 5 times with SAME idempotency key
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/v1/payments/webhook \
    -H "X-Idempotency-Key: same_key" \
    -d "{...}"
done

# Check logs - should show:
# - First request: "✓ Webhook processed"
# - Subsequent requests: "Cache hit" or "Idempotency hit"
```

### Scenario 2: Test State Machine

```bash
# Create payment (status: INITIATED)

# Try invalid transition: INITIATED -> CAPTURED (should fail)
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "X-Idempotency-Key: invalid" \
  -d '{
    "payment_intent_id": "...",
    "status": "CAPTURED",
    ...
  }'

# Expected: HTTP 400 with "invalid_transition" error

# Valid transition: INITIATED -> AUTHORIZED -> CAPTURED
# 1. INITIATED -> AUTHORIZED (succeeds)
# 2. AUTHORIZED -> CAPTURED (succeeds)
```

### Scenario 3: Test Out-of-Order Webhooks

```bash
# Send newer webhook first (timestamp: now)
curl -X POST ... -d '{"timestamp": "2025-11-21T10:05:00Z", "status": "AUTHORIZED"}'

# Send older webhook (timestamp: 5 minutes ago)
curl -X POST ... -d '{"timestamp": "2025-11-21T10:00:00Z", "status": "INITIATED"}'

# Expected: Second webhook is ignored with "out_of_order" status
```

## Troubleshooting

### Services Won't Start

```bash
# Check if ports are already in use
netstat -an | grep LISTEN | grep -E "(8000|8001|8002|8003|8004|5432|6379|5672)"

# Stop all containers and restart
docker-compose down
docker-compose up -d
```

### Database Connection Errors

```bash
# Wait for PostgreSQL to initialize
docker-compose logs postgres

# Look for: "database system is ready to accept connections"

# Restart affected services
docker-compose restart donation-service payment-service
```

### Services Not Appearing in Prometheus

```bash
# Check Prometheus targets
# Open http://localhost:9090/targets

# Services should be in "UP" state
# If "DOWN", check service health endpoints

# Restart Prometheus
docker-compose restart prometheus
```

### No Traces in Jaeger

```bash
# Check Jaeger collector
docker-compose logs jaeger

# Check if services can reach Jaeger
docker-compose exec donation-service ping jaeger

# Verify OTEL_EXPORTER_OTLP_ENDPOINT is set correctly
docker-compose exec donation-service env | grep OTEL
```

## Next Steps

1. **Explore the Architecture**: Read `ARCHITECTURE.md` for detailed technical design
2. **Customize the Platform**: Modify service configurations in `docker-compose.yml`
3. **Add More Services**: Follow the microservice pattern to add new features
4. **Deploy to Production**: Use Kubernetes manifests (see deployment docs)
5. **Set Up CI/CD**: Configure GitHub Actions workflow for your repository

## Quick Reference

| Service | Port | Endpoint |
|---------|------|----------|
| API Gateway | 8000 | http://localhost:8000 |
| Donation Service | 8001 | http://localhost:8001 |
| Payment Service | 8002 | http://localhost:8002 |
| Totals Service | 8003 | http://localhost:8003 |
| Notification Service | 8004 | http://localhost:8004 |
| Grafana | 3000 | http://localhost:3000 |
| Prometheus | 9090 | http://localhost:9090 |
| Jaeger UI | 16686 | http://localhost:16686 |
| RabbitMQ Management | 15672 | http://localhost:15672 |

## Support

For issues or questions:
1. Check the logs: `docker-compose logs [service]`
2. Review the architecture: `ARCHITECTURE.md`
3. Run health checks: `curl http://localhost:8000/health`
4. Check metrics: Grafana dashboard

Happy testing! 🚀

