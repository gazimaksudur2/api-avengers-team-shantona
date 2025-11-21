# Docker Compose Complete Guide
## CareForAll Platform - Microservices Deployment

This guide provides everything you need to run and operate the complete CareForAll platform using Docker Compose.

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [System Architecture](#system-architecture)
3. [Prerequisites](#prerequisites)
4. [Configuration Files](#configuration-files)
5. [Running the Platform](#running-the-platform)
6. [Service Ports](#service-ports)
7. [Scaling Services](#scaling-services)
8. [Environment Modes](#environment-modes)
9. [Health Checks](#health-checks)
10. [Troubleshooting](#troubleshooting)
11. [Production Deployment](#production-deployment)
12. [Monitoring & Observability](#monitoring--observability)

---

## 🚀 Quick Start

### Fastest Way to Get Running

```bash
# Clone the repository
cd API_avengers

# Start all services
make start

# Or use docker-compose directly
docker-compose up -d

# Check service health
make health

# View logs
make logs
```

**That's it!** The platform will be running at http://localhost:8000

---

## 🏗️ System Architecture

### Services Overview

| Service | Replicas | Port | Database | Purpose |
|---------|----------|------|----------|---------|
| **API Gateway** | 1 | 8000 | - | Nginx reverse proxy, load balancer |
| **Donation Service** | 3 | 8001 | donations_db | Manage donations with Transactional Outbox |
| **Payment Service** | 3 | 8002 | payments_db | Handle payments with idempotency & state machine |
| **Totals Service** | 2 | 8003 | donations_db | Real-time totals with 3-level caching |
| **Notification Service** | 2 | 8004 | notifications_db | Send notifications via email |
| **Campaign Service** | 2 | 8005 | campaigns_db | Manage fundraising campaigns |
| **Bank Service** | 2 | 8006 | bank_db | P2P transfers with double-entry bookkeeping |
| **Admin Service** | 1 | 8007 | admin_db | Admin dashboard with JWT auth |

### Infrastructure Components

| Component | Port(s) | Purpose |
|-----------|---------|---------|
| **PostgreSQL** | 5432 | Primary database (6 databases) |
| **Redis** | 6379 | Caching & idempotency |
| **RabbitMQ** | 5672, 15672 | Message broker & event bus |
| **Prometheus** | 9090 | Metrics collection |
| **Grafana** | 3000 | Visualization dashboards |
| **Jaeger** | 16686, 4317, 4318 | Distributed tracing |

---

## 📦 Prerequisites

### Required Software

```bash
# Check versions
docker --version          # Requires 20.10+
docker-compose --version  # Requires 1.29+

# Minimum system requirements
# - RAM: 8GB (16GB recommended)
# - CPU: 4 cores (8 recommended)
# - Disk: 10GB free space
```

### Installation

#### Windows
```powershell
# Install Docker Desktop
# https://www.docker.com/products/docker-desktop

# Verify installation
docker --version
docker-compose --version
```

#### Linux
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

#### macOS
```bash
# Install Docker Desktop
brew install --cask docker

# Start Docker Desktop from Applications
```

---

## 📁 Configuration Files

### Docker Compose Files

```
docker-compose.yml           # Base configuration (all services)
docker-compose.dev.yml       # Development overrides
docker-compose.prod.yml      # Production overrides
```

### Supporting Files

```
init-db.sh                   # PostgreSQL database initialization
api-gateway/nginx.conf       # Nginx configuration
.dockerignore               # Files to exclude from Docker builds
env.example                 # Environment variables template
```

---

## 🎮 Running the Platform

### Method 1: Using Makefile (Recommended)

```bash
# Start all services
make start

# Stop all services
make stop

# Restart services
make restart

# View logs
make logs

# View specific service logs
make logs-donation
make logs-payment

# Check health
make health

# Clean up (removes all data)
make clean

# Rebuild images
make build

# Show all available commands
make help
```

### Method 2: Using Docker Compose Directly

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# View specific service
docker-compose logs -f donation-service

# Check status
docker-compose ps

# Rebuild a specific service
docker-compose build donation-service

# Restart a specific service
docker-compose restart payment-service
```

### Method 3: Selective Service Startup

```bash
# Start only infrastructure
docker-compose up -d postgres redis rabbitmq

# Start specific services
docker-compose up -d donation-service payment-service

# Start observability stack
docker-compose up -d prometheus grafana jaeger
```

---

## 🔌 Service Ports

### External Access URLs

```bash
# Main API Endpoints
http://localhost:8000                    # API Gateway (all services)
http://localhost:8000/api/v1/donations   # Donations
http://localhost:8000/api/v1/payments    # Payments
http://localhost:8000/api/v1/totals      # Totals
http://localhost:8000/api/v1/campaigns   # Campaigns
http://localhost:8000/api/v1/bank        # Banking
http://localhost:8000/api/v1/admin       # Admin

# Observability
http://localhost:3000                    # Grafana (admin/admin)
http://localhost:9090                    # Prometheus
http://localhost:16686                   # Jaeger Tracing

# Infrastructure
http://localhost:15672                   # RabbitMQ Management (guest/guest)
localhost:5432                           # PostgreSQL (postgres/postgres)
localhost:6379                           # Redis

# Direct Service Access (Development)
http://localhost:8001                    # Donation Service
http://localhost:8002                    # Payment Service
http://localhost:8003                    # Totals Service
http://localhost:8004                    # Notification Service
http://localhost:8005                    # Campaign Service
http://localhost:8006                    # Bank Service
http://localhost:8007                    # Admin Service
```

---

## ⚖️ Scaling Services

### Using Docker Compose

```bash
# Scale donation service to 5 replicas
docker-compose up -d --scale donation-service=5

# Scale multiple services
docker-compose up -d \
  --scale donation-service=5 \
  --scale payment-service=5 \
  --scale totals-service=3

# Using Makefile
make scale-donation REPLICAS=5
make scale-payment REPLICAS=5
```

### Default Replica Configuration

| Service | Development | Production |
|---------|-------------|------------|
| Donation | 3 → 1 | 5 |
| Payment | 3 → 1 | 5 |
| Totals | 2 → 1 | 3 |
| Notification | 2 → 1 | 3 |
| Campaign | 2 → 1 | 3 |
| Bank | 2 → 1 | 3 |
| Admin | 1 | 2 |

### Load Balancing

Nginx automatically load balances across all replicas using **least_conn** algorithm:

```nginx
upstream donation_service {
    least_conn;  # Route to server with fewest connections
    server donation-service:8001 max_fails=3 fail_timeout=30s;
}
```

---

## 🔧 Environment Modes

### Development Mode

```bash
# Start with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Features:
# - Hot reload enabled
# - Debug logging
# - Direct port access to all services
# - PgAdmin on port 5050
# - Redis Commander on port 8081
# - Single replica per service
```

**Development Tools:**

| Tool | URL | Credentials |
|------|-----|-------------|
| PgAdmin | http://localhost:5050 | admin@careforall.local / admin |
| Redis Commander | http://localhost:8081 | - |

### Production Mode

```bash
# Start with production overrides
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Features:
# - More replicas (5x donation, 5x payment)
# - Resource limits & reservations
# - Structured logging (JSON, rotated)
# - 30-day Prometheus retention
# - Restart policies
# - No debug tools
```

### Default Mode (Balanced)

```bash
# Best for testing and demos
docker-compose up -d

# Features:
# - 3x donation service
# - 3x payment service
# - 2x other services
# - All observability enabled
# - Reasonable resource usage
```

---

## 🏥 Health Checks

### Automated Health Checks

All services have built-in health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

### Manual Health Checks

```bash
# Check all services
make health

# Or manually
curl http://localhost:8000/health         # API Gateway
curl http://localhost:8001/health         # Donation Service
curl http://localhost:8002/health         # Payment Service
curl http://localhost:8003/health         # Totals Service
curl http://localhost:8004/health         # Notification Service
curl http://localhost:8005/health         # Campaign Service
curl http://localhost:8006/health         # Bank Service
curl http://localhost:8007/health         # Admin Service

# Check infrastructure
docker-compose ps                          # All containers
redis-cli -h localhost ping                # Redis
psql -h localhost -U postgres -c "SELECT 1" # PostgreSQL
```

### Service Dependencies

Services wait for dependencies to be healthy before starting:

```yaml
depends_on:
  postgres:
    condition: service_healthy
  rabbitmq:
    condition: service_healthy
  redis:
    condition: service_healthy
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Error: port is already allocated
# Solution: Check what's using the port
netstat -ano | findstr :8000   # Windows
lsof -i :8000                  # Linux/Mac

# Kill the process or change the port in docker-compose.yml
```

#### 2. Container Fails to Start

```bash
# Check logs
docker-compose logs donation-service

# Check service health
docker-compose ps

# Restart specific service
docker-compose restart donation-service

# Rebuild if code changed
docker-compose up -d --build donation-service
```

#### 3. Database Connection Errors

```bash
# Wait for PostgreSQL to be ready
docker-compose logs postgres

# Check if databases were created
docker-compose exec postgres psql -U postgres -l

# Recreate databases
docker-compose down -v
docker-compose up -d
```

#### 4. Out of Memory

```bash
# Check Docker resources
docker stats

# Increase Docker memory
# Docker Desktop → Settings → Resources → Memory (16GB recommended)

# Or reduce replicas
docker-compose up -d --scale donation-service=1 --scale payment-service=1
```

#### 5. Network Issues

```bash
# Recreate networks
docker-compose down
docker network prune
docker-compose up -d
```

### Debug Commands

```bash
# View container logs
docker-compose logs -f --tail=100 donation-service

# Execute command in container
docker-compose exec donation-service bash

# Check environment variables
docker-compose exec donation-service env

# Test network connectivity
docker-compose exec donation-service ping postgres
docker-compose exec donation-service curl http://rabbitmq:15672

# View resource usage
docker stats

# Inspect container
docker inspect careforall-donation-service-1
```

---

## 🚀 Production Deployment

### Pre-Deployment Checklist

```bash
✓ Set environment variables
✓ Change default passwords
✓ Configure external database (optional)
✓ Set up SSL/TLS certificates
✓ Configure backup strategy
✓ Set up monitoring alerts
✓ Review resource limits
✓ Test disaster recovery
```

### Production Setup

#### 1. Environment Variables

```bash
# Copy and edit environment file
cp env.example .env

# Critical variables to change:
# - JWT_SECRET_KEY
# - POSTGRES_PASSWORD
# - GRAFANA_ADMIN_PASSWORD
# - STRIPE_API_KEY (production key)
# - SENDGRID_API_KEY
```

#### 2. Start Production Stack

```bash
# Build images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify health
docker-compose ps
make health
```

#### 3. SSL/TLS Configuration

Add to `docker-compose.prod.yml`:

```yaml
api-gateway:
  volumes:
    - ./ssl/cert.pem:/etc/nginx/ssl/cert.pem:ro
    - ./ssl/key.pem:/etc/nginx/ssl/key.pem:ro
  ports:
    - "443:443"
```

Update `nginx.conf`:

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    # ... rest of config
}
```

#### 4. Database Backups

```bash
# Manual backup
make backup-db

# Automated backup (add to crontab)
0 2 * * * cd /path/to/project && make backup-db

# Restore from backup
make restore-db FILE=backup_20241121_020000.sql
```

#### 5. Log Management

Production mode uses JSON logging with rotation:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

View logs:

```bash
# Real-time logs
docker-compose logs -f

# Export logs
docker-compose logs --no-color > system.log
```

---

## 📊 Monitoring & Observability

### Prometheus Metrics

Access: http://localhost:9090

**Key Metrics:**
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration
- `database_connections` - DB connection pool
- `cache_hit_rate` - Redis cache performance

**Useful Queries:**
```promql
# Request rate (per second)
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

### Grafana Dashboards

Access: http://localhost:3000 (admin/admin)

**Pre-configured Dashboards:**
1. System Overview - All services health
2. Service Performance - Request rates, latency
3. Database Metrics - Connections, queries
4. Cache Performance - Hit rates, evictions

### Jaeger Tracing

Access: http://localhost:16686

**Features:**
- End-to-end request tracing
- Service dependency graph
- Performance bottleneck identification
- Error trace analysis

**Example: Find slow requests**
1. Open Jaeger UI
2. Select service: `donation-service`
3. Click "Find Traces"
4. Filter by duration > 1s

### RabbitMQ Management

Access: http://localhost:15672 (guest/guest)

**Monitor:**
- Queue depths
- Message rates
- Consumer status
- Connection health

---

## 📚 Additional Resources

### Quick Reference Commands

```bash
# Start everything
make start

# Stop everything
make stop

# View logs
make logs

# Health check
make health

# Scale service
make scale-donation REPLICAS=5

# Run tests
make test

# Clean everything
make clean

# Rebuild
make build

# Open dashboards
make dashboard    # Grafana
make metrics      # Prometheus
make traces       # Jaeger
make rabbitmq     # RabbitMQ
```

### Configuration Files Location

```
.
├── docker-compose.yml              # Main configuration
├── docker-compose.dev.yml          # Development overrides
├── docker-compose.prod.yml         # Production overrides
├── .dockerignore                   # Build exclusions
├── init-db.sh                      # Database initialization
├── Makefile                        # Convenience commands
├── env.example                     # Environment template
└── api-gateway/
    └── nginx.conf                  # API Gateway config
```

### Service Health Endpoints

All services expose:
- `GET /health` - Basic health check
- `GET /metrics` - Prometheus metrics
- `GET /docs` - OpenAPI documentation (development)

---

## 🎯 Best Practices

### Development

1. **Use development mode** for hot reload
2. **Check logs frequently** during development
3. **Use direct ports** to bypass API gateway
4. **Scale down replicas** to save resources
5. **Use PgAdmin** for database inspection

### Testing

1. **Start fresh** with `make clean && make start`
2. **Check health** before running tests
3. **Use demo flow** to verify end-to-end: `make demo`
4. **Run stress tests**: `make stress`
5. **Monitor metrics** during load tests

### Production

1. **Change all default passwords**
2. **Use external database** for production data
3. **Configure SSL/TLS** for HTTPS
4. **Set up monitoring alerts**
5. **Enable log aggregation**
6. **Regular backups** with `make backup-db`
7. **Test disaster recovery** procedures
8. **Monitor resource usage** with `docker stats`

---

## 🆘 Getting Help

### Check Service Status

```bash
docker-compose ps
make health
docker-compose logs --tail=50
```

### Common Commands

```bash
# Restart a misbehaving service
docker-compose restart payment-service

# Rebuild after code changes
docker-compose up -d --build donation-service

# Reset everything
make clean
make start

# View resource usage
docker stats
```

### Debug Mode

```bash
# Run service in foreground with logs
docker-compose up donation-service

# Execute shell in container
docker-compose exec donation-service bash

# Check environment
docker-compose exec donation-service env | grep DATABASE
```

---

## 📝 Summary

### Quick Commands Cheatsheet

| Task | Command |
|------|---------|
| Start all | `make start` or `docker-compose up -d` |
| Stop all | `make stop` or `docker-compose down` |
| View logs | `make logs` or `docker-compose logs -f` |
| Check health | `make health` |
| Scale service | `make scale-donation REPLICAS=5` |
| Rebuild | `make build` or `docker-compose build` |
| Clean up | `make clean` or `docker-compose down -v` |
| Development | `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up` |
| Production | `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d` |

### Architecture at a Glance

```
                    ┌─────────────────┐
                    │   API Gateway   │ :8000
                    │     (Nginx)     │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌─────▼────┐        ┌─────▼────┐
   │Donation │         │ Payment  │        │  Totals  │
   │Service  │         │ Service  │        │ Service  │
   │(x3)     │         │  (x3)    │        │  (x2)    │
   └────┬────┘         └─────┬────┘        └─────┬────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌─────▼────┐        ┌─────▼────┐
   │Postgres │         │  Redis   │        │ RabbitMQ │
   │  (x6)   │         │          │        │          │
   └─────────┘         └──────────┘        └──────────┘
```

---

**CareForAll Platform** - Scalable Microservices Architecture 🚀

For more information, see:
- [README.md](README.md) - Project overview
- [ARCHITECTURE_AND_DESIGN.md](documentation/ARCHITECTURE_AND_DESIGN.md) - Architecture details
- [env.example](env.example) - Environment configuration

