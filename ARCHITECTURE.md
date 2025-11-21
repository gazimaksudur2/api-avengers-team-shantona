# CareForAll - Next-Generation Fundraising Platform Architecture

## Executive Summary

This document outlines the architecture for a resilient, scalable microservices-based fundraising platform that addresses the critical failures of the legacy system.

## Core Problems Solved

| Problem | Solution |
|---------|----------|
| **Lack of Idempotency** | Idempotency keys + Redis cache for webhook deduplication |
| **Reliability Issues** | Transactional Outbox pattern + Message Broker (RabbitMQ) |
| **State Control** | State machine with version tracking and event ordering |
| **Observability Gap** | OpenTelemetry + Prometheus + Grafana + Jaeger |
| **Performance Bottleneck** | Materialized view pattern + Redis caching for totals |

## Microservices Architecture

### 1. API Gateway (Kong/Nginx)
**Responsibility**: Single entry point, routing, rate limiting, authentication
- Load balancing across service replicas
- Request validation and transformation
- JWT authentication middleware
- Rate limiting per client

### 2. Donation Service
**Responsibility**: Core donation orchestration and history
- **Port**: 8001
- **Database**: PostgreSQL (donations, pledges, audit logs)
- **Key Features**:
  - Create donation pledges
  - Maintain complete donation history
  - Transactional Outbox for reliable event publishing
  - Full audit trail

**Data Model**:
```sql
CREATE TABLE donations (
    id UUID PRIMARY KEY,
    campaign_id UUID NOT NULL,
    donor_email VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(20) NOT NULL, -- PENDING, COMPLETED, FAILED, REFUNDED
    payment_intent_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    version INT DEFAULT 1,
    metadata JSONB
);

CREATE TABLE outbox_events (
    id BIGSERIAL PRIMARY KEY,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    retry_count INT DEFAULT 0
);

CREATE INDEX idx_outbox_unprocessed ON outbox_events (created_at) 
WHERE processed_at IS NULL;
```

**API Endpoints**:
- `POST /api/v1/donations` - Create donation pledge
- `GET /api/v1/donations/:id` - Get donation details
- `GET /api/v1/donations/history` - Get donor history (by email)
- `PATCH /api/v1/donations/:id/status` - Update donation status (internal)

### 3. Payment Service
**Responsibility**: Payment processing, webhook handling, idempotency
- **Port**: 8002
- **Database**: PostgreSQL (payment transactions, idempotency records)
- **Cache**: Redis (idempotency key cache)
- **Key Features**:
  - Stripe/PayPal integration
  - Webhook deduplication using idempotency keys
  - Payment state machine with versioning
  - Retry logic with exponential backoff

**Data Model**:
```sql
CREATE TABLE payment_transactions (
    id UUID PRIMARY KEY,
    donation_id UUID NOT NULL,
    payment_intent_id VARCHAR(255) UNIQUE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(20) NOT NULL, -- INITIATED, AUTHORIZED, CAPTURED, FAILED, REFUNDED
    gateway VARCHAR(50) NOT NULL, -- stripe, paypal
    gateway_response JSONB,
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    response_body TEXT,
    response_status INT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_idempotency_expires ON idempotency_keys (expires_at);

-- State transition audit
CREATE TABLE payment_state_history (
    id BIGSERIAL PRIMARY KEY,
    payment_id UUID NOT NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    event_id VARCHAR(255),
    event_timestamp TIMESTAMP NOT NULL,
    received_at TIMESTAMP DEFAULT NOW(),
    version INT NOT NULL
);
```

**State Machine**:
```
INITIATED → AUTHORIZED → CAPTURED ✓
         ↓            ↓
       FAILED      REFUNDED
```

**API Endpoints**:
- `POST /api/v1/payments/intent` - Create payment intent
- `POST /api/v1/payments/webhook` - Handle payment gateway webhooks (idempotent)
- `GET /api/v1/payments/:id` - Get payment status
- `POST /api/v1/payments/:id/refund` - Initiate refund

### 4. Totals Service
**Responsibility**: Optimized fundraising analytics and totals
- **Port**: 8003
- **Database**: PostgreSQL (materialized views)
- **Cache**: Redis (hot path caching with TTL)
- **Key Features**:
  - Materialized view for pre-aggregated totals
  - Multi-level caching strategy
  - Event-driven cache invalidation
  - Real-time and eventual consistency modes

**Data Model**:
```sql
CREATE MATERIALIZED VIEW campaign_totals AS
SELECT 
    campaign_id,
    COUNT(*) as total_donations,
    SUM(amount) as total_amount,
    COUNT(DISTINCT donor_email) as unique_donors,
    MAX(updated_at) as last_updated
FROM donations
WHERE status = 'COMPLETED'
GROUP BY campaign_id;

CREATE UNIQUE INDEX idx_campaign_totals ON campaign_totals (campaign_id);

-- Refresh strategy: incremental updates via trigger or scheduled job
```

**Caching Strategy**:
- L1: Redis cache (30s TTL) for ultra-fast reads
- L2: Materialized view (refreshed every 5 minutes or on-demand)
- L3: Base table (fallback)

**API Endpoints**:
- `GET /api/v1/totals/campaigns/:id` - Get campaign totals (cached)
- `GET /api/v1/totals/campaigns/:id?realtime=true` - Force real-time calculation
- `POST /api/v1/totals/refresh` - Trigger cache/view refresh (internal)

### 5. Notification Service
**Responsibility**: Send donor confirmations and alerts
- **Port**: 8004
- **Database**: PostgreSQL (notification logs)
- **Key Features**:
  - Email notifications (SendGrid/AWS SES)
  - SMS notifications (Twilio)
  - Webhook notifications
  - Retry with exponential backoff

**Data Model**:
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    donation_id UUID NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL, -- EMAIL, SMS, WEBHOOK
    status VARCHAR(20) NOT NULL, -- PENDING, SENT, FAILED
    template_id VARCHAR(100),
    payload JSONB,
    retry_count INT DEFAULT 0,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**API Endpoints**:
- `POST /api/v1/notifications/send` - Send notification (internal)
- `GET /api/v1/notifications/:donationId` - Get notification status

### 6. Message Broker (RabbitMQ)
**Responsibility**: Asynchronous event distribution
- **Exchanges**:
  - `donations.events` (topic) - Donation lifecycle events
  - `payments.events` (topic) - Payment status changes
- **Queues**:
  - `totals.queue` - Consumed by Totals Service
  - `notifications.queue` - Consumed by Notification Service
  - `audit.queue` - For audit logging

## Event Flow Diagram

```
┌─────────────────┐
│   API Gateway   │
│   (Port 8000)   │
└────────┬────────┘
         │
    1. POST /donations
         │
         ▼
┌─────────────────────┐
│  Donation Service   │──┐
│    (Port 8001)      │  │ 2. Write donation + outbox event
└─────────┬───────────┘  │    (SINGLE TRANSACTION)
          │              │
          │              ▼
          │         PostgreSQL
          │
          │ 3. Outbox Processor
          │    polls & publishes
          ▼
    ┌──────────┐
    │ RabbitMQ │
    └────┬─────┘
         │
    ┌────┴────────────────────┐
    │                         │
    ▼                         ▼
┌──────────────┐      ┌──────────────┐
│Payment Service│      │Notification  │
│ (Port 8002)  │      │   Service    │
└──────┬───────┘      └──────────────┘
       │
  4. Create payment
     intent with
     gateway
       │
       ▼
┌──────────────┐
│   Stripe     │
│   Webhook    │
└──────┬───────┘
       │
  5. POST /webhook
     (with idempotency key)
       │
       ▼
Payment Service validates:
- Check Redis cache for duplicate
- Verify state transition validity
- Update with optimistic locking
       │
       ▼
  Publish payment.completed
       │
       ▼
┌──────────────┐
│Totals Service│
│ (Port 8003)  │
└──────────────┘
  Invalidate cache &
  refresh materialized view
```

## Scalability Strategy

### Horizontal Scaling
```yaml
# docker-compose.yml excerpt
services:
  donation-service:
    deploy:
      replicas: 3
    
  payment-service:
    deploy:
      replicas: 3
    
  totals-service:
    deploy:
      replicas: 2
```

### Database Scaling
- **Read Replicas**: Route read-heavy queries (e.g., history, totals) to replicas
- **Connection Pooling**: PgBouncer for connection management
- **Partitioning**: Partition donations table by created_at for time-series queries

### Caching Strategy
- **Redis Cluster**: For distributed caching across replicas
- **Cache-aside pattern**: Application-level caching with TTL
- **Cache warming**: Pre-populate cache for popular campaigns

## Fault Tolerance Mechanisms

### 1. Idempotency (Payment Service)
```python
@app.post("/webhook")
async def handle_webhook(request: Request, idempotency_key: str):
    # Check cache first (fast path)
    cached = redis.get(f"idem:{idempotency_key}")
    if cached:
        return cached
    
    # Check database (slower path)
    existing = db.query(IdempotencyKey).filter_by(key=idempotency_key).first()
    if existing:
        return Response(existing.response_body, existing.response_status)
    
    # Process request
    response = process_webhook(request)
    
    # Store idempotency record (cache + DB)
    save_idempotency_record(idempotency_key, response)
    return response
```

### 2. Outbox Pattern (Donation Service)
```python
@app.post("/donations")
async def create_donation(donation: DonationRequest):
    async with db.transaction():
        # 1. Write donation
        donation_record = insert_donation(donation)
        
        # 2. Write outbox event (SAME TRANSACTION)
        outbox_event = {
            "aggregate_id": donation_record.id,
            "event_type": "DonationCreated",
            "payload": donation_record.to_dict()
        }
        insert_outbox_event(outbox_event)
        
        # Commit atomically - both or neither
    
    return donation_record

# Separate process polls outbox
async def outbox_processor():
    while True:
        events = fetch_unprocessed_events(limit=100)
        for event in events:
            try:
                publish_to_rabbitmq(event)
                mark_as_processed(event.id)
            except Exception as e:
                increment_retry_count(event.id)
                log_error(e)
```

### 3. State Machine with Versioning (Payment Service)
```python
VALID_TRANSITIONS = {
    "INITIATED": ["AUTHORIZED", "FAILED"],
    "AUTHORIZED": ["CAPTURED", "FAILED", "REFUNDED"],
    "CAPTURED": ["REFUNDED"],
    "FAILED": [],
    "REFUNDED": []
}

async def update_payment_status(payment_id, new_status, event_timestamp, event_id):
    async with db.transaction():
        # Lock row for update
        payment = db.query(Payment).with_for_update().get(payment_id)
        
        # Check if this event is older than current state
        if event_timestamp < payment.updated_at:
            log.warn(f"Ignoring out-of-order event {event_id}")
            return payment
        
        # Validate state transition
        if new_status not in VALID_TRANSITIONS[payment.status]:
            raise InvalidStateTransition(payment.status, new_status)
        
        # Update with optimistic locking
        payment.status = new_status
        payment.version += 1
        payment.updated_at = event_timestamp
        
        # Audit log
        insert_state_history(payment_id, payment.status, new_status, event_id)
        
        db.commit()
        return payment
```

## Observability Architecture

### Distributed Tracing (OpenTelemetry + Jaeger)
Every request gets a trace context propagated across services:
```
Trace ID: 7f8a3c2d1e9b4a5f
├─ Span: API Gateway (8ms)
├─ Span: Donation Service (45ms)
│  ├─ Span: DB Insert (12ms)
│  └─ Span: Outbox Insert (8ms)
├─ Span: RabbitMQ Publish (5ms)
└─ Span: Payment Service (120ms)
   └─ Span: Stripe API Call (95ms)
```

### Metrics (Prometheus)
Key metrics collected:
- `http_requests_total{service, endpoint, status}`
- `http_request_duration_seconds{service, endpoint}`
- `donation_created_total{campaign_id}`
- `payment_webhook_processed_total{status, idempotency_hit}`
- `cache_hit_ratio{service, cache_type}`
- `outbox_processing_lag_seconds`

### Logging (ELK Stack / Loki)
Structured JSON logs with trace context:
```json
{
  "timestamp": "2025-11-21T10:30:45Z",
  "service": "payment-service",
  "level": "INFO",
  "trace_id": "7f8a3c2d1e9b4a5f",
  "span_id": "4a5f6b7c",
  "message": "Webhook processed",
  "idempotency_key": "evt_1234",
  "payment_id": "uuid-here",
  "duration_ms": 120
}
```

### Dashboards (Grafana)
1. **System Health**: CPU, memory, request rate, error rate
2. **Business Metrics**: Donations/minute, total raised, conversion rate
3. **Performance**: P50/P95/P99 latencies, cache hit rates
4. **Reliability**: Outbox lag, webhook retry counts, service availability

## API Gateway Configuration

### Load Balancing Strategy
- Algorithm: Round-robin with health checks
- Health check: `GET /health` every 10s
- Circuit breaker: Open after 5 consecutive failures

### Rate Limiting
- Global: 10,000 requests/minute
- Per IP: 100 requests/minute
- Per API key: 1,000 requests/minute

### Security
- JWT authentication for all endpoints
- API key validation
- Request/response size limits
- CORS configuration

## Deployment Architecture

### Docker Compose Services
```
- nginx (API Gateway) - 1 instance
- donation-service - 3 replicas
- payment-service - 3 replicas
- totals-service - 2 replicas
- notification-service - 2 replicas
- postgres - 1 instance (with replication in production)
- redis - 1 instance (cluster in production)
- rabbitmq - 1 instance (cluster in production)
- prometheus - 1 instance
- grafana - 1 instance
- jaeger - 1 instance
```

### Network Architecture
```
┌─────────────────────────────────────┐
│         Public Network              │
│                                     │
│  ┌──────────────────────────────┐  │
│  │      API Gateway (Nginx)     │  │
│  │         Port 8000            │  │
│  └──────────────┬───────────────┘  │
└─────────────────┼───────────────────┘
                  │
┌─────────────────┼───────────────────┐
│    Internal Network (Backend)       │
│                 │                   │
│  ┌──────────────┼──────────────┐   │
│  │   Service Mesh              │   │
│  │   - donation-service x3     │   │
│  │   - payment-service x3      │   │
│  │   - totals-service x2       │   │
│  │   - notification-service x2 │   │
│  └──────────────┬──────────────┘   │
│                 │                   │
│  ┌──────────────┼──────────────┐   │
│  │   Data Layer                │   │
│  │   - PostgreSQL              │   │
│  │   - Redis                   │   │
│  │   - RabbitMQ                │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Observability Stack        │   │
│  │  - Prometheus               │   │
│  │  - Grafana (Port 3000)      │   │
│  │  - Jaeger (Port 16686)      │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## Summary

This architecture addresses all critical failures:
- ✅ **Idempotency**: Redis + DB-backed deduplication
- ✅ **Reliability**: Transactional Outbox pattern
- ✅ **State Control**: State machine + versioning + event ordering
- ✅ **Observability**: Full tracing, metrics, and logging
- ✅ **Performance**: Materialized views + multi-level caching

The system is designed to handle 1000+ req/s with horizontal scaling, comprehensive fault tolerance, and complete visibility into system behavior.

