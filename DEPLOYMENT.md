# Deployment Guide

This guide covers deploying the CareForAll platform to production environments.

## Production Considerations

### 1. Database

#### PostgreSQL High Availability

```yaml
# Use managed database service (AWS RDS, Google Cloud SQL, etc.)
services:
  donation-service:
    environment:
      - DATABASE_URL=postgresql://user:pass@production-db.example.com:5432/donations_db
      
# Or set up replication
master-db:
  image: postgres:15
  environment:
    - POSTGRES_REPLICATION_MODE=master
    
slave-db:
  image: postgres:15
  environment:
    - POSTGRES_REPLICATION_MODE=slave
    - POSTGRES_MASTER_HOST=master-db
```

**Read Replicas**:
- Route read-heavy queries (totals, history) to replicas
- Write operations go to master
- Use PgBouncer for connection pooling

### 2. Redis

#### Redis Cluster for High Availability

```yaml
# Use managed Redis (AWS ElastiCache, Redis Cloud, etc.)
services:
  donation-service:
    environment:
      - REDIS_URL=redis://production-redis.example.com:6379
      
# Or set up Redis Sentinel
redis-master:
  image: redis:7
  
redis-sentinel:
  image: redis:7
  command: redis-sentinel /etc/redis/sentinel.conf
```

### 3. RabbitMQ

#### RabbitMQ Cluster

```yaml
# Use managed service (CloudAMQP, AWS MQ, etc.)
# Or set up cluster
rabbitmq-1:
  image: rabbitmq:3-management
  environment:
    - RABBITMQ_ERLANG_COOKIE=secret_cookie
    
rabbitmq-2:
  image: rabbitmq:3-management
  environment:
    - RABBITMQ_ERLANG_COOKIE=secret_cookie
  depends_on:
    - rabbitmq-1
```

### 4. Secrets Management

**Don't commit secrets to Git!**

Use environment-specific secret management:

```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id careforall/stripe-key

# Kubernetes Secrets
kubectl create secret generic careforall-secrets \
  --from-literal=stripe-api-key=sk_live_xxx \
  --from-literal=database-password=xxx

# Docker Swarm Secrets
echo "sk_live_xxx" | docker secret create stripe-api-key -
```

### 5. Load Balancing

#### Nginx Configuration (Production)

```nginx
upstream donation_service {
    least_conn;
    server donation-service-1:8001 max_fails=3 fail_timeout=30s;
    server donation-service-2:8001 max_fails=3 fail_timeout=30s;
    server donation-service-3:8001 max_fails=3 fail_timeout=30s;
}

# Add SSL/TLS
server {
    listen 443 ssl http2;
    server_name api.careforall.com;
    
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    
    # ... rest of configuration
}
```

## Kubernetes Deployment

### Deployment Example

```yaml
# donation-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: donation-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: donation-service
  template:
    metadata:
      labels:
        app: donation-service
    spec:
      containers:
      - name: donation-service
        image: ghcr.io/org/careforall-donation-service:v1.0.0
        ports:
        - containerPort: 8001
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: careforall-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: careforall-config
              key: redis-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: donation-service
spec:
  selector:
    app: donation-service
  ports:
  - port: 8001
    targetPort: 8001
  type: ClusterIP
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: donation-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: donation-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Docker Swarm Deployment

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml careforall

# Scale services
docker service scale careforall_donation-service=5
docker service scale careforall_payment-service=5

# Update service
docker service update --image ghcr.io/org/donation-service:v1.1.0 careforall_donation-service

# View logs
docker service logs -f careforall_donation-service
```

## Monitoring in Production

### Prometheus Configuration

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'production'
    environment: 'prod'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - 'alerts.yml'

scrape_configs:
  # Service discovery for Kubernetes
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

### Alert Rules

```yaml
# alerts.yml
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
          description: "Error rate is {{ $value }} for {{ $labels.service }}"
      
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P95 latency is {{ $value }}s for {{ $labels.service }}"
      
      - alert: LowCacheHitRate
        expr: cache_hit_ratio < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit rate is low"
          description: "Cache hit rate is {{ $value }} for {{ $labels.cache_type }}"
      
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
          description: "{{ $labels.job }} is down"
```

## Backup Strategy

### Database Backups

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup all databases
docker exec postgres pg_dumpall -c -U postgres | gzip > $BACKUP_DIR/backup_$TIMESTAMP.sql.gz

# Upload to S3
aws s3 cp $BACKUP_DIR/backup_$TIMESTAMP.sql.gz s3://careforall-backups/

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

# Schedule with cron
# 0 2 * * * /path/to/backup.sh
```

### Disaster Recovery Plan

1. **Database**: Restore from S3 backup
2. **Redis**: Rebuild cache (ephemeral data)
3. **RabbitMQ**: Messages are persisted, no action needed
4. **Services**: Redeploy from Docker registry

## Performance Tuning

### Database Connection Pooling

```python
# Use PgBouncer
DATABASE_URL=postgresql://user:pass@pgbouncer:6432/db

# PgBouncer config
[databases]
donations_db = host=postgres port=5432 dbname=donations_db

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

### Redis Configuration

```conf
# redis.conf (production)
maxmemory 2gb
maxmemory-policy allkeys-lru
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

### Nginx Tuning

```nginx
worker_processes auto;
worker_connections 4096;

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript;
}
```

## Security Hardening

### 1. API Rate Limiting

```nginx
# Stricter rate limits in production
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
limit_req zone=api_limit burst=20 nodelay;
```

### 2. HTTPS/TLS

```bash
# Use Let's Encrypt
certbot certonly --webroot -w /var/www/html -d api.careforall.com

# Auto-renewal
0 0 * * * certbot renew --quiet
```

### 3. Network Segmentation

```yaml
# Separate public and private networks
networks:
  public:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access
```

### 4. Secrets Rotation

```bash
# Rotate database password
ALTER USER postgres WITH PASSWORD 'new_password';

# Update secrets
kubectl set env deployment/donation-service DATABASE_PASSWORD=new_password
```

## Cost Optimization

### 1. Right-size Resources

```yaml
# Start small, scale based on metrics
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "250m"
```

### 2. Use Spot Instances (AWS/GCP)

```yaml
# Kubernetes node selector
nodeSelector:
  node-type: spot
```

### 3. Cache Optimization

- Increase cache TTL for stable data
- Use cache warming for popular campaigns
- Monitor cache hit ratio

## Rollback Strategy

```bash
# Kubernetes rollback
kubectl rollout undo deployment/donation-service

# Docker Swarm rollback
docker service rollback careforall_donation-service

# Manual rollback
docker service update --image ghcr.io/org/donation-service:v1.0.0 careforall_donation-service
```

## Health Checks & Monitoring

### 1. Uptime Monitoring

Use services like:
- UptimeRobot
- Pingdom
- AWS CloudWatch Synthetics

### 2. Log Aggregation

```yaml
# Use ELK Stack or managed service
logging:
  driver: "fluentd"
  options:
    fluentd-address: "localhost:24224"
    tag: "careforall.{{.Name}}"
```

### 3. APM (Application Performance Monitoring)

Consider:
- New Relic
- Datadog
- Elastic APM

## Compliance & Auditing

### PCI DSS Compliance

- Never store full card numbers
- Use tokenization via Stripe
- Encrypt data at rest and in transit
- Regular security audits

### GDPR Compliance

- Right to be forgotten: Delete donor data
- Data portability: Export donor history
- Consent management: Track consent in metadata

## Production Checklist

- [ ] All secrets stored in secret manager
- [ ] TLS/SSL certificates configured
- [ ] Database backups automated
- [ ] Monitoring and alerting set up
- [ ] Rate limiting configured
- [ ] Firewall rules configured
- [ ] Health checks enabled
- [ ] Auto-scaling configured
- [ ] CI/CD pipeline tested
- [ ] Disaster recovery plan documented
- [ ] Security audit completed
- [ ] Load testing completed
- [ ] Compliance requirements met

## Support

For production deployment assistance, refer to:
- Cloud provider documentation
- Kubernetes documentation
- Docker Swarm documentation
- Contact DevOps team

