#!/bin/bash
# Bash script to start CareForAll Platform
# Run this script: chmod +x start-platform.sh && ./start-platform.sh

set -e

echo -e "\033[0;32m🚀 Starting CareForAll Platform...\033[0m"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "\033[0;31m❌ Docker is not running!\033[0m"
    echo -e "\033[0;33mPlease start Docker and try again.\033[0m"
    exit 1
fi

echo -e "\033[0;32m✅ Docker is running\033[0m"
echo ""

# Check for mode parameter
MODE="${1:-default}"

# Start services based on mode
case "$MODE" in
    dev)
        echo -e "\033[0;36m📦 Starting in DEVELOPMENT mode...\033[0m"
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
        ;;
    prod)
        echo -e "\033[0;36m🏭 Starting in PRODUCTION mode...\033[0m"
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
        ;;
    *)
        echo -e "\033[0;36m📦 Starting in DEFAULT mode...\033[0m"
        docker-compose up -d
        ;;
esac

echo ""
echo -e "\033[0;33m⏳ Waiting for services to be ready...\033[0m"
sleep 30

echo ""
echo -e "\033[0;36m🏥 Checking service health...\033[0m"

# Function to check health
check_health() {
    local name=$1
    local url=$2
    echo -n "  $name: "
    if curl -f -s "$url" > /dev/null 2>&1; then
        echo -e "\033[0;32m✅ Healthy\033[0m"
    else
        echo -e "\033[0;31m❌ Unhealthy\033[0m"
    fi
}

check_health "API Gateway        " "http://localhost:8000/health"
check_health "Donation Service   " "http://localhost:8001/health"
check_health "Payment Service    " "http://localhost:8002/health"
check_health "Totals Service     " "http://localhost:8003/health"
check_health "Notification Service" "http://localhost:8004/health"
check_health "Campaign Service   " "http://localhost:8005/health"
check_health "Bank Service       " "http://localhost:8006/health"
check_health "Admin Service      " "http://localhost:8007/health"

echo ""
echo -e "\033[0;32m========================================"
echo "✅ Platform is running!"
echo "========================================\033[0m"
echo ""

echo -e "\033[0;36m📍 Access Points:\033[0m"
echo "   API Gateway:  http://localhost:8000"
echo "   Grafana:      http://localhost:3000 (admin/admin)"
echo "   Prometheus:   http://localhost:9090"
echo "   Jaeger:       http://localhost:16686"
echo "   RabbitMQ:     http://localhost:15672 (guest/guest)"
echo ""

echo -e "\033[0;36m📊 View logs:\033[0m"
echo "   docker-compose logs -f"
echo ""

echo -e "\033[0;36m🛑 Stop platform:\033[0m"
echo "   docker-compose down"
echo ""

echo -e "\033[0;36m📚 Documentation:\033[0m"
echo "   See DOCKER_GUIDE.md for complete guide"
echo ""

