#!/bin/bash
# Bash Script to Check All Services Health
# Usage: ./scripts/check-all-services.sh

echo ""
echo "🔍 CareForAll Platform Health Check"
echo "=================================================="
echo ""

services=(
    "API Gateway:http://localhost:8000/health"
    "Donation Service:http://localhost:8001/health"
    "Payment Service:http://localhost:8002/health"
    "Totals Service:http://localhost:8003/health"
    "Notification Service:http://localhost:8004/health"
    "Prometheus:http://localhost:9090/-/healthy"
    "Grafana:http://localhost:3000/api/health"
    "Jaeger:http://localhost:16686/"
    "RabbitMQ:http://localhost:15672/"
)

all_healthy=true

for service in "${services[@]}"; do
    IFS=':' read -r name url rest <<< "$service"
    
    if curl -f -s -o /dev/null -w "%{http_code}" "$url" --max-time 5 | grep -q "^2"; then
        echo "✓ $name: Healthy"
    else
        echo "✗ $name: Unhealthy"
        all_healthy=false
    fi
done

echo ""

if [ "$all_healthy" = true ]; then
    echo "🎉 All services are healthy!"
else
    echo "⚠️  Some services are unhealthy. Check logs with:"
    echo "   docker-compose logs [service-name]"
fi

echo ""
echo "📊 Quick Links:"
echo "   Grafana:    http://localhost:3000 (admin/admin)"
echo "   Prometheus: http://localhost:9090"
echo "   Jaeger:     http://localhost:16686"
echo "   RabbitMQ:   http://localhost:15672 (guest/guest)"
echo ""

