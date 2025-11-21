# CareForAll Platform Makefile

.PHONY: help start stop restart logs build test clean health demo stress

help: ## Show this help message
	@echo "CareForAll Platform - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

start: ## Start all services
	@echo "🚀 Starting CareForAll Platform..."
	docker-compose up -d
	@echo "⏳ Waiting for services to be ready..."
	@sleep 30
	@$(MAKE) health
	@echo ""
	@echo "✅ Platform is running!"
	@echo "   API Gateway: http://localhost:8000"
	@echo "   Grafana: http://localhost:3000 (admin/admin)"
	@echo "   Jaeger: http://localhost:16686"
	@echo "   Prometheus: http://localhost:9090"

stop: ## Stop all services
	@echo "🛑 Stopping CareForAll Platform..."
	docker-compose down

restart: ## Restart all services
	@echo "🔄 Restarting CareForAll Platform..."
	docker-compose restart

logs: ## Show logs from all services
	docker-compose logs -f

logs-donation: ## Show logs from donation service
	docker-compose logs -f donation-service

logs-payment: ## Show logs from payment service
	docker-compose logs -f payment-service

logs-totals: ## Show logs from totals service
	docker-compose logs -f totals-service

logs-notification: ## Show logs from notification service
	docker-compose logs -f notification-service

logs-campaign: ## Show logs from campaign service
	docker-compose logs -f campaign-service

logs-bank: ## Show logs from bank service
	docker-compose logs -f bank-service

logs-admin: ## Show logs from admin service
	docker-compose logs -f admin-service

build: ## Build all Docker images
	@echo "🔨 Building Docker images..."
	docker-compose build

test: ## Run all tests
	@echo "🧪 Running tests..."
	@echo "Testing Donation Service..."
	docker-compose run --rm donation-service pytest test_main.py -v
	@echo ""
	@echo "Testing Payment Service..."
	docker-compose run --rm payment-service pytest test_main.py -v
	@echo ""
	@echo "✅ All tests passed!"

test-donation: ## Run donation service tests
	docker-compose run --rm donation-service pytest test_main.py -v

test-payment: ## Run payment service tests
	docker-compose run --rm payment-service pytest test_main.py -v

test-idempotency: ## Run idempotency tests only
	docker-compose run --rm payment-service pytest test_main.py::test_webhook_idempotency_same_key -v

health: ## Check health of all services
	@echo "🏥 Checking service health..."
	@echo -n "  API Gateway: "
	@curl -s http://localhost:8000/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
	@echo -n "  Donation Service: "
	@curl -s http://localhost:8001/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
	@echo -n "  Payment Service: "
	@curl -s http://localhost:8002/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
	@echo -n "  Totals Service: "
	@curl -s http://localhost:8003/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
	@echo -n "  Notification Service: "
	@curl -s http://localhost:8004/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
	@echo -n "  Campaign Service: "
	@curl -s http://localhost:8005/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
	@echo -n "  Bank Service: "
	@curl -s http://localhost:8006/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"
	@echo -n "  Admin Service: "
	@curl -s http://localhost:8007/health > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy"

demo: ## Run the demo flow
	@echo "🎬 Running demo flow..."
	@chmod +x test-scenarios/demo-flow.sh
	@./test-scenarios/demo-flow.sh

stress: ## Run stress tests
	@echo "⚡ Running stress tests..."
	@chmod +x test-scenarios/stress-test.sh
	@./test-scenarios/stress-test.sh

clean: ## Clean up all containers, volumes, and data
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	@echo "✅ Cleanup complete!"

ps: ## Show status of all services
	docker-compose ps

scale-donation: ## Scale donation service (make scale-donation REPLICAS=5)
	docker-compose up -d --scale donation-service=$(REPLICAS)

scale-payment: ## Scale payment service (make scale-payment REPLICAS=5)
	docker-compose up -d --scale payment-service=$(REPLICAS)

scale-totals: ## Scale totals service (make scale-totals REPLICAS=3)
	docker-compose up -d --scale totals-service=$(REPLICAS)

scale-notification: ## Scale notification service (make scale-notification REPLICAS=3)
	docker-compose up -d --scale notification-service=$(REPLICAS)

scale-campaign: ## Scale campaign service (make scale-campaign REPLICAS=3)
	docker-compose up -d --scale campaign-service=$(REPLICAS)

scale-bank: ## Scale bank service (make scale-bank REPLICAS=3)
	docker-compose up -d --scale bank-service=$(REPLICAS)

scale-all: ## Scale all services (make scale-all REPLICAS=5)
	docker-compose up -d --scale donation-service=$(REPLICAS) --scale payment-service=$(REPLICAS) --scale totals-service=$(REPLICAS) --scale notification-service=$(REPLICAS) --scale campaign-service=$(REPLICAS) --scale bank-service=$(REPLICAS)

metrics: ## Open Prometheus in browser
	@echo "Opening Prometheus..."
	@open http://localhost:9090 2>/dev/null || xdg-open http://localhost:9090 2>/dev/null || echo "Please open http://localhost:9090"

dashboard: ## Open Grafana dashboard in browser
	@echo "Opening Grafana..."
	@open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || echo "Please open http://localhost:3000"

traces: ## Open Jaeger traces in browser
	@echo "Opening Jaeger..."
	@open http://localhost:16686 2>/dev/null || xdg-open http://localhost:16686 2>/dev/null || echo "Please open http://localhost:16686"

rabbitmq: ## Open RabbitMQ management in browser
	@echo "Opening RabbitMQ..."
	@open http://localhost:15672 2>/dev/null || xdg-open http://localhost:15672 2>/dev/null || echo "Please open http://localhost:15672"

lint: ## Run linting on all services
	@echo "🔍 Running linting..."
	@for service in donation-service payment-service totals-service notification-service; do \
		echo "Linting $$service..."; \
		docker-compose run --rm $$service sh -c "pip install flake8 && flake8 main.py"; \
	done

install: ## Install development dependencies
	@echo "📦 Installing dependencies..."
	@cd services/donation-service && pip install -r requirements.txt
	@cd services/payment-service && pip install -r requirements.txt
	@cd services/totals-service && pip install -r requirements.txt
	@cd services/notification-service && pip install -r requirements.txt

dev: ## Start in development mode with live reload
	docker-compose up

backup-db: ## Backup PostgreSQL database
	@echo "💾 Backing up database..."
	docker-compose exec -T postgres pg_dumpall -c -U postgres > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Database backed up!"

restore-db: ## Restore PostgreSQL database (make restore-db FILE=backup.sql)
	@echo "📥 Restoring database from $(FILE)..."
	cat $(FILE) | docker-compose exec -T postgres psql -U postgres
	@echo "✅ Database restored!"

