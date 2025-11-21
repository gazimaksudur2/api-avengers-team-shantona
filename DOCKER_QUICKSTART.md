# Docker Compose Quick Start
## Get CareForAll Running in 3 Steps

---

## ⚡ 3-Step Quick Start

### Step 1: Start Docker

**Windows**: Start Docker Desktop  
**Linux/Mac**: Ensure Docker daemon is running

### Step 2: Run the Platform

#### Option A: Using Quick Start Script (Recommended)

**Windows:**
```powershell
.\start-platform.ps1
```

**Linux/Mac:**
```bash
chmod +x start-platform.sh
./start-platform.sh
```

#### Option B: Using Make
```bash
make start
```

#### Option C: Using Docker Compose Directly
```bash
docker-compose up -d
```

### Step 3: Access the Platform

Open your browser:
- **API Gateway**: http://localhost:8000
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger Tracing**: http://localhost:16686

---

## 🎯 That's It!

Your complete platform with 7 microservices, 3 databases, message queue, cache, and full observability stack is now running.

---

## 📊 Verify Everything is Running

```bash
# Check service health
make health

# Or manually
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
# ... etc

# View logs
make logs

# View specific service
docker-compose logs -f donation-service
```

---

## 🚀 Test the Platform

### Create a Donation

```bash
curl -X POST http://localhost:8000/api/v1/donations \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "camp-123",
    "donor_email": "donor@example.com",
    "donor_name": "John Doe",
    "amount": 100.00,
    "currency": "USD",
    "extra_data": {"source": "web"}
  }'
```

### Create a Payment

```bash
curl -X POST http://localhost:8000/api/v1/payments/intent \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "currency": "USD",
    "donation_id": "donation-id-from-above"
  }'
```

### Get Totals

```bash
curl http://localhost:8000/api/v1/totals
```

### Create a Campaign

```bash
curl -X POST http://localhost:8000/api/v1/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Help Build Schools",
    "description": "Fundraising for education",
    "goal_amount": 50000.00,
    "currency": "USD",
    "organization": "CareForAll Foundation"
  }'
```

---

## 🎮 Different Modes

### Development Mode
```bash
# Windows
.\start-platform.ps1 -Mode dev

# Linux/Mac
./start-platform.sh dev

# Or
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

**Features:**
- Hot reload
- Direct port access
- PgAdmin: http://localhost:5050
- Redis Commander: http://localhost:8081
- Single replica per service

### Production Mode
```bash
# Windows
.\start-platform.ps1 -Mode prod

# Linux/Mac
./start-platform.sh prod

# Or
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Features:**
- 5x donation service
- 5x payment service
- Resource limits
- Structured logging
- No debug tools

---

## 🛑 Stop the Platform

```bash
# Option 1: Using Make
make stop

# Option 2: Using Docker Compose
docker-compose down

# Option 3: Stop and remove all data
make clean
# or
docker-compose down -v
```

---

## 📈 Scale Services

### Scale Specific Service
```bash
# Using Make
make scale-donation REPLICAS=5
make scale-payment REPLICAS=5

# Using Docker Compose
docker-compose up -d --scale donation-service=5
docker-compose up -d --scale payment-service=5
```

### Scale All Services
```bash
make scale-all REPLICAS=5
```

### Check Scaling
```bash
docker-compose ps
```

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs donation-service

# Restart service
docker-compose restart donation-service

# Rebuild service
docker-compose up -d --build donation-service
```

### Port Already in Use

```bash
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000

# Change port in docker-compose.yml or kill the process
```

### Out of Memory

```bash
# Check resource usage
docker stats

# Increase Docker memory in Docker Desktop settings
# Or scale down replicas
docker-compose up -d --scale donation-service=1
```

### Clean Reset

```bash
# Stop everything and remove data
make clean

# Or
docker-compose down -v
docker system prune -a

# Start fresh
make start
```

---

## 📚 Learn More

- **[DOCKER_GUIDE.md](DOCKER_GUIDE.md)** - Complete Docker Compose guide
- **[README.md](README.md)** - Project overview
- **[ARCHITECTURE_AND_DESIGN.md](documentation/ARCHITECTURE_AND_DESIGN.md)** - System architecture
- **[Makefile](Makefile)** - All available commands

---

## 🎯 Key Endpoints

### Services (via API Gateway)
```
http://localhost:8000/api/v1/donations    # Donation Service
http://localhost:8000/api/v1/payments     # Payment Service
http://localhost:8000/api/v1/totals       # Totals Service
http://localhost:8000/api/v1/campaigns    # Campaign Service
http://localhost:8000/api/v1/bank         # Bank Service
http://localhost:8000/api/v1/admin        # Admin Service
```

### Observability
```
http://localhost:3000      # Grafana (admin/admin)
http://localhost:9090      # Prometheus
http://localhost:16686     # Jaeger Tracing
http://localhost:15672     # RabbitMQ Management (guest/guest)
```

### Direct Service Access (Development)
```
http://localhost:8001      # Donation Service
http://localhost:8002      # Payment Service
http://localhost:8003      # Totals Service
http://localhost:8004      # Notification Service
http://localhost:8005      # Campaign Service
http://localhost:8006      # Bank Service
http://localhost:8007      # Admin Service
```

---

## 💡 Pro Tips

1. **Always check health** before running tests: `make health`
2. **Use Make commands** for convenience: `make help`
3. **Monitor resources** during development: `docker stats`
4. **Check logs frequently**: `make logs`
5. **Scale based on load**: Start with defaults, scale as needed
6. **Use dev mode** for development with hot reload
7. **Backup before cleaning**: `make backup-db` before `make clean`

---

## ✅ Success Checklist

After starting, verify:
- [ ] All services show "Healthy" in `make health`
- [ ] Can access Grafana at http://localhost:3000
- [ ] Can create a donation via API
- [ ] Can view totals
- [ ] RabbitMQ shows queues in management UI
- [ ] Jaeger shows traces
- [ ] Prometheus shows metrics

---

## 🆘 Quick Help

```bash
# See all available commands
make help

# Check service status
docker-compose ps

# View logs
make logs

# Restart everything
make restart

# Clean and start fresh
make clean && make start
```

---

**Need more help?** Check [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for comprehensive documentation.

