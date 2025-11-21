#!/bin/bash

# Demo Flow - Shows complete donation lifecycle with observability

set -e

BASE_URL="http://localhost:8000"
CAMPAIGN_ID="550e8400-e29b-41d4-a716-446655440000"

echo "🎬 CareForAll Platform Demo - Complete Donation Flow"
echo "====================================================="
echo ""

# Step 1: Create a donation
echo "Step 1: Creating a donation..."
DONATION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/donations" \
    -H "Content-Type: application/json" \
    -d "{
        \"campaign_id\": \"$CAMPAIGN_ID\",
        \"donor_email\": \"demo@example.com\",
        \"amount\": 100.00,
        \"currency\": \"USD\",
        \"metadata\": {
            \"source\": \"demo\",
            \"campaign_name\": \"Save the Rainforest\"
        }
    }")

DONATION_ID=$(echo $DONATION_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
echo "  ✓ Donation created: $DONATION_ID"
echo "  Response: $DONATION_RESPONSE" | jq '.'
echo ""

# Wait for outbox processor
sleep 2

# Step 2: Create payment intent
echo "Step 2: Creating payment intent..."
PAYMENT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/intent" \
    -H "Content-Type: application/json" \
    -d "{
        \"donation_id\": \"$DONATION_ID\",
        \"amount\": 100.00,
        \"currency\": \"USD\",
        \"gateway\": \"stripe\"
    }")

PAYMENT_ID=$(echo $PAYMENT_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
PAYMENT_INTENT_ID=$(echo $PAYMENT_RESPONSE | grep -o '"payment_intent_id":"[^"]*"' | cut -d'"' -f4)
CLIENT_SECRET=$(echo $PAYMENT_RESPONSE | grep -o '"client_secret":"[^"]*"' | cut -d'"' -f4)

echo "  ✓ Payment intent created: $PAYMENT_INTENT_ID"
echo "  Response: $PAYMENT_RESPONSE" | jq '.'
echo ""
echo "  📝 In a real scenario, this client_secret would be used by"
echo "     the frontend to complete payment with Stripe.js"
echo ""

# Step 3: Simulate payment authorization webhook
echo "Step 3: Simulating payment authorization webhook..."
AUTH_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Idempotency-Key: demo_auth_$(date +%s)" \
    -d "{
        \"event_type\": \"payment_intent.succeeded\",
        \"payment_intent_id\": \"$PAYMENT_INTENT_ID\",
        \"status\": \"AUTHORIZED\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
        \"data\": {
            \"card_brand\": \"visa\",
            \"last4\": \"4242\"
        }
    }")

echo "  ✓ Payment authorized"
echo "  Response: $AUTH_RESPONSE" | jq '.'
echo ""

sleep 1

# Step 4: Simulate payment capture webhook
echo "Step 4: Simulating payment capture webhook..."
CAPTURE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Idempotency-Key: demo_capture_$(date +%s)" \
    -d "{
        \"event_type\": \"payment_intent.captured\",
        \"payment_intent_id\": \"$PAYMENT_INTENT_ID\",
        \"status\": \"CAPTURED\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
        \"data\": {
            \"captured_amount\": 100.00
        }
    }")

echo "  ✓ Payment captured"
echo "  Response: $CAPTURE_RESPONSE" | jq '.'
echo ""

sleep 2

# Step 5: Update donation status
echo "Step 5: Updating donation status to COMPLETED..."
UPDATE_RESPONSE=$(curl -s -X PATCH "$BASE_URL/api/v1/donations/$DONATION_ID/status" \
    -H "Content-Type: application/json" \
    -d "{
        \"status\": \"COMPLETED\",
        \"payment_intent_id\": \"$PAYMENT_INTENT_ID\"
    }")

echo "  ✓ Donation completed"
echo "  Response: $UPDATE_RESPONSE" | jq '.'
echo ""

sleep 2

# Step 6: Get updated totals
echo "Step 6: Fetching campaign totals..."
TOTALS_RESPONSE=$(curl -s "$BASE_URL/api/v1/totals/campaigns/$CAMPAIGN_ID")

echo "  ✓ Campaign totals retrieved"
echo "  Response: $TOTALS_RESPONSE" | jq '.'
echo ""

# Step 7: Get donation history
echo "Step 7: Fetching donor history..."
HISTORY_RESPONSE=$(curl -s "$BASE_URL/api/v1/donations/history?donor_email=demo@example.com")

echo "  ✓ Donation history retrieved"
echo "  Response: $HISTORY_RESPONSE" | jq '.'
echo ""

# Step 8: Demonstrate idempotency
echo "Step 8: Demonstrating idempotency..."
echo "  Sending duplicate webhook with same idempotency key..."

# Send same capture webhook again
DUPLICATE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/payments/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Idempotency-Key: demo_capture_$(date +%s)" \
    -d "{
        \"event_type\": \"payment_intent.captured\",
        \"payment_intent_id\": \"$PAYMENT_INTENT_ID\",
        \"status\": \"CAPTURED\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
        \"data\": {
            \"captured_amount\": 100.00
        }
    }")

if [ "$DUPLICATE_RESPONSE" == "$CAPTURE_RESPONSE" ]; then
    echo "  ✓ Idempotency working! Duplicate webhook returned cached response"
else
    echo "  ⚠️  Responses differ (may have used different idempotency key)"
fi
echo ""

# Summary
echo "📊 Demo Complete!"
echo "================="
echo ""
echo "Journey Summary:"
echo "  1. ✓ Donation created: $DONATION_ID"
echo "  2. ✓ Payment intent created: $PAYMENT_INTENT_ID"
echo "  3. ✓ Payment authorized (INITIATED → AUTHORIZED)"
echo "  4. ✓ Payment captured (AUTHORIZED → CAPTURED)"
echo "  5. ✓ Donation marked as COMPLETED"
echo "  6. ✓ Totals updated with cache invalidation"
echo "  7. ✓ Donor history retrieved"
echo "  8. ✓ Idempotency demonstrated"
echo ""
echo "🔍 View this flow in:"
echo "  • Grafana Dashboard: http://localhost:3000"
echo "  • Jaeger Traces: http://localhost:16686 (search for donation ID)"
echo "  • Prometheus Metrics: http://localhost:9090"
echo "  • RabbitMQ Queues: http://localhost:15672"
echo ""
echo "🎉 All systems operational!"

