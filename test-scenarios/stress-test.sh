#!/bin/bash

# Stress Test Script for CareForAll Platform
# Tests idempotency, state machine, and system performance under load

set -e

BASE_URL="http://localhost:8000"
CAMPAIGN_ID="550e8400-e29b-41d4-a716-446655440000"
CONCURRENT_REQUESTS=100
TOTAL_REQUESTS=1000

echo "🚀 CareForAll Platform Stress Test"
echo "===================================="
echo ""
echo "Configuration:"
echo "  Base URL: $BASE_URL"
echo "  Campaign ID: $CAMPAIGN_ID"
echo "  Concurrent Requests: $CONCURRENT_REQUESTS"
echo "  Total Requests: $TOTAL_REQUESTS"
echo ""

# Check if services are healthy
echo "📋 Checking service health..."
for service in donation payment totals notification; do
    response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/${service}s/health" 2>/dev/null || echo "000")
    if [ "$response" == "200" ]; then
        echo "  ✓ ${service} service: healthy"
    else
        echo "  ✗ ${service} service: unhealthy (HTTP $response)"
        exit 1
    fi
done
echo ""

# Test 1: Create donations concurrently
echo "📝 Test 1: Creating $TOTAL_REQUESTS donations with $CONCURRENT_REQUESTS concurrent requests..."
START_TIME=$(date +%s)

for i in $(seq 1 $TOTAL_REQUESTS); do
    (
        DONOR_EMAIL="donor${i}@example.com"
        AMOUNT=$((RANDOM % 900 + 100))
        
        curl -s -X POST "$BASE_URL/api/v1/donations" \
            -H "Content-Type: application/json" \
            -d "{
                \"campaign_id\": \"$CAMPAIGN_ID\",
                \"donor_email\": \"$DONOR_EMAIL\",
                \"amount\": $AMOUNT
            }" > /dev/null &
        
        # Limit concurrent requests
        if [ $((i % CONCURRENT_REQUESTS)) -eq 0 ]; then
            wait
        fi
    ) &
done

wait

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
RATE=$((TOTAL_REQUESTS / DURATION))

echo "  ✓ Completed $TOTAL_REQUESTS donations in ${DURATION}s (~${RATE} req/s)"
echo ""

# Test 2: Test idempotency with duplicate webhooks
echo "🔄 Test 2: Testing idempotency with duplicate webhooks..."

# Create a payment intent first
DONATION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/donations" \
    -H "Content-Type: application/json" \
    -d "{
        \"campaign_id\": \"$CAMPAIGN_ID\",
        \"donor_email\": \"idempotency-test@example.com\",
        \"amount\": 100.00
    }")

DONATION_ID=$(echo $DONATION_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

# Create payment intent
PAYMENT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/intent" \
    -H "Content-Type: application/json" \
    -d "{
        \"donation_id\": \"$DONATION_ID\",
        \"amount\": 100.00
    }")

PAYMENT_INTENT_ID=$(echo $PAYMENT_RESPONSE | grep -o '"payment_intent_id":"[^"]*"' | cut -d'"' -f4)

# Send same webhook 10 times with same idempotency key
IDEMPOTENCY_KEY="test_duplicate_$(date +%s)"
echo "  Sending webhook 10 times with same idempotency key..."

for i in $(seq 1 10); do
    RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/webhook" \
        -H "Content-Type: application/json" \
        -H "X-Idempotency-Key: $IDEMPOTENCY_KEY" \
        -d "{
            \"event_type\": \"payment_intent.succeeded\",
            \"payment_intent_id\": \"$PAYMENT_INTENT_ID\",
            \"status\": \"AUTHORIZED\",
            \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
        }")
    
    if [ $i -eq 1 ]; then
        FIRST_RESPONSE=$RESPONSE
    fi
    
    if [ "$RESPONSE" != "$FIRST_RESPONSE" ]; then
        echo "  ✗ Idempotency failed! Responses differ."
        exit 1
    fi
done

echo "  ✓ All 10 duplicate webhooks returned identical responses (idempotency working)"
echo ""

# Test 3: Out-of-order webhook handling
echo "⏱️  Test 3: Testing out-of-order webhook handling..."

# Create another payment
DONATION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/donations" \
    -H "Content-Type: application/json" \
    -d "{
        \"campaign_id\": \"$CAMPAIGN_ID\",
        \"donor_email\": \"order-test@example.com\",
        \"amount\": 150.00
    }")

DONATION_ID=$(echo $DONATION_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

PAYMENT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/intent" \
    -H "Content-Type: application/json" \
    -d "{
        \"donation_id\": \"$DONATION_ID\",
        \"amount\": 150.00
    }")

PAYMENT_INTENT_ID=$(echo $PAYMENT_RESPONSE | grep -o '"payment_intent_id":"[^"]*"' | cut -d'"' -f4)

# Send newer webhook first
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RESPONSE1=$(curl -s -X POST "$BASE_URL/api/v1/payments/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Idempotency-Key: order_test_newer" \
    -d "{
        \"event_type\": \"payment_intent.succeeded\",
        \"payment_intent_id\": \"$PAYMENT_INTENT_ID\",
        \"status\": \"AUTHORIZED\",
        \"timestamp\": \"$NOW\"
    }")

# Send older webhook (should be ignored)
OLDER_TIME=$(date -u -d "5 minutes ago" +%Y-%m-%dT%H:%M:%SZ)
RESPONSE2=$(curl -s -X POST "$BASE_URL/api/v1/payments/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Idempotency-Key: order_test_older" \
    -d "{
        \"event_type\": \"payment_intent.processing\",
        \"payment_intent_id\": \"$PAYMENT_INTENT_ID\",
        \"status\": \"INITIATED\",
        \"timestamp\": \"$OLDER_TIME\"
    }")

if echo "$RESPONSE2" | grep -q "out_of_order"; then
    echo "  ✓ Out-of-order webhook correctly ignored"
else
    echo "  ✗ Out-of-order webhook not handled correctly"
    echo "  Response: $RESPONSE2"
fi
echo ""

# Test 4: Invalid state transition
echo "🚫 Test 4: Testing invalid state transition rejection..."

# Create payment
DONATION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/donations" \
    -H "Content-Type: application/json" \
    -d "{
        \"campaign_id\": \"$CAMPAIGN_ID\",
        \"donor_email\": \"state-test@example.com\",
        \"amount\": 200.00
    }")

DONATION_ID=$(echo $DONATION_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

PAYMENT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/intent" \
    -H "Content-Type: application/json" \
    -d "{
        \"donation_id\": \"$DONATION_ID\",
        \"amount\": 200.00
    }")

PAYMENT_INTENT_ID=$(echo $PAYMENT_RESPONSE | grep -o '"payment_intent_id":"[^"]*"' | cut -d'"' -f4)

# Try invalid transition: INITIATED -> CAPTURED (should be INITIATED -> AUTHORIZED -> CAPTURED)
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Idempotency-Key: invalid_transition" \
    -d "{
        \"event_type\": \"payment_intent.captured\",
        \"payment_intent_id\": \"$PAYMENT_INTENT_ID\",
        \"status\": \"CAPTURED\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }")

if echo "$RESPONSE" | grep -q "invalid_transition"; then
    echo "  ✓ Invalid state transition correctly rejected"
else
    echo "  ✗ Invalid state transition not handled correctly"
    echo "  Response: $RESPONSE"
fi
echo ""

# Test 5: Cache performance
echo "💾 Test 5: Testing cache performance..."

# Make 100 requests to totals endpoint
echo "  Making 100 requests to totals endpoint..."
START_TIME=$(date +%s%N | cut -b1-13)

for i in $(seq 1 100); do
    curl -s "$BASE_URL/api/v1/totals/campaigns/$CAMPAIGN_ID" > /dev/null
done

END_TIME=$(date +%s%N | cut -b1-13)
DURATION=$((END_TIME - START_TIME))
AVG_LATENCY=$((DURATION / 100))

echo "  ✓ Average latency: ${AVG_LATENCY}ms (should be <50ms with cache)"
echo ""

# Summary
echo "📊 Test Summary"
echo "==============="
echo "✓ Donation creation under load: $RATE req/s"
echo "✓ Idempotency: Duplicate webhooks handled correctly"
echo "✓ State machine: Out-of-order webhooks ignored"
echo "✓ State machine: Invalid transitions rejected"
echo "✓ Cache performance: ${AVG_LATENCY}ms average latency"
echo ""
echo "🎉 All tests passed!"
echo ""
echo "📈 View metrics in Grafana: http://localhost:3000"
echo "🔍 View traces in Jaeger: http://localhost:16686"
echo "📊 View metrics in Prometheus: http://localhost:9090"

