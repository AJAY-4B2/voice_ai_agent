# 2Care.ai Voice AI Agent — Deployment Guide

## Deployment Options

### Option 1: Docker (Recommended for Production)

#### Prerequisites
- Docker & Docker Compose
- Redis or cloud Redis instance
- LLM API keys (Anthropic/OpenAI)

#### Deploy with Docker Compose

```bash
# 1. Update .env with production values
nano .env

# 2. Build and start
docker-compose up -d --build

# 3. Verify
curl http://localhost:8000/api/health
```

**docker-compose.yml** includes:
- FastAPI service on port 8000
- Redis service on port 6379
- Volume mounts for code updates
- Environment variable injection

#### Production Docker Compose

For production, use explicit resource limits:

```yaml
services:
  api:
    # ... existing config
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### Option 2: Kubernetes

#### Build Image

```bash
docker build -t voice-ai-agent:latest .
docker tag voice-ai-agent:latest myregistry.azurecr.io/voice-ai-agent:latest
docker push myregistry.azurecr.io/voice-ai-agent:latest
```

#### Deploy to Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-ai-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voice-ai-agent
  template:
    metadata:
      labels:
        app: voice-ai-agent
    spec:
      containers:
      - name: api
        image: myregistry.azurecr.io/voice-ai-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: anthropic-key
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          limits:
            memory: "2Gi"
            cpu: "1"
          requests:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: voice-ai-agent-svc
spec:
  type: LoadBalancer
  selector:
    app: voice-ai-agent
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
```

Deploy:
```bash
kubectl apply -f deployment.yaml
kubectl create secret generic llm-secrets --from-literal=anthropic-key=$ANTHROPIC_API_KEY
```

### Option 3: Cloud Platforms

#### AWS ECS

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster voice-ai \
  --service-name voice-ai-agent \
  --task-definition voice-ai-agent:1 \
  --desired-count 3
```

#### Google Cloud Run

```bash
gcloud run deploy voice-ai-agent \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY,REDIS_URL=$REDIS_URL"
```

#### Azure Container Instances

```bash
az container create \
  --resource-group mygroup \
  --name voice-ai-agent \
  --image voice-ai-agent:latest \
  --cpu 2 --memory 2 \
  --environment-variables ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
```

## Environment Configuration

### Production .env Template

```env
# LLM Configuration
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-20241022
ANTHROPIC_API_KEY=sk-ant-xxxxxx
OPENAI_API_KEY=sk-xxxxxx

# Speech Services
WHISPER_MODEL=whisper-1
TTS_PROVIDER=openai

# Redis (Cloud managed)
REDIS_URL=redis://:password@redis-host.redis.cache.windows.net:6379/0

# Database (optional, for persistence)
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/appointments

# App Configuration
APP_ENV=production
LOG_LEVEL=INFO
```

## Monitoring & Observability

### Prometheus Metrics

Metrics are exported on `/metrics`:

```bash
curl http://localhost:8000/metrics
```

**Key metrics:**
- `voice_agent_request_duration_seconds` - Request latency histogram
- `voice_agent_requests_total` - Request counter
- `voice_agent_appointments_total` - Appointment operations counter
- `voice_agent_errors_total` - Error counter

### Log Aggregation

Logs can be aggregated using ELK, Splunk, or cloud logging:

```python
# Structured logging example
logger.info("appointment_booked", extra={
    "patient_id": patient_id,
    "doctor_id": doctor_id,
    "slot": slot,
    "latency_ms": latency
})
```

### Health Checks

**Liveness Probe:**
```bash
curl http://localhost:8000/api/health
```

Response: `{"status": "healthy"}`

## Performance Tuning

### Uvicorn Workers

For production, increase worker count:

```bash
uvicorn backend.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --host 0.0.0.0 \
  --port 8000
```

### Redis Connection Pooling

Update in `backend/main.py`:

```python
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
app.state.redis = await aioredis.from_url(
    redis_url,
    encoding="utf-8",
    decode_responses=True,
    max_connections=50,  # Increase for high traffic
    socket_keepalive=True,
)
```

### Session TTL Tuning

In `memory/session_memory/session_store.py`:

```python
SESSION_TTL = 3600  # 1 hour (adjust based on usage patterns)
```

## Database Migration (if using PostgreSQL)

```bash
# Initialize Alembic (one-time)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

## Troubleshooting Deployment

### Container won't start
```bash
docker logs <container-id>
```

Check:
- Redis connectivity
- API key validity
- Port availability

### High latency
```bash
# Monitor metrics
curl http://localhost:8000/metrics | grep latency
```

Check:
- Redis latency
- LLM API response time
- Network connectivity

### Memory leaks
```bash
# Monitor container memory
docker stats <container-id>
```

Solutions:
- Increase allocated memory
- Check for unbounded caches
- Review session TTL settings

## Scaling Strategy

### Horizontal Scaling

1. **Stateless API Servers**
   - Multiple FastAPI instances behind load balancer
   - Redis shared session store

2. **Redis Clustering**
   - Redis Sentinel for high availability
   - Redis Cluster for sharding

3. **Load Balancer** (Nginx/HAProxy)
   ```nginx
   upstream voice_agent {
       server api-1:8000;
       server api-2:8000;
       server api-3:8000;
   }
   
   server {
       listen 80;
       location / {
           proxy_pass http://voice_agent;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   ```

### Vertical Scaling
- Increase CPU cores
- Increase memory allocation
- Use faster Redis instance
- Optimize database queries

## Security Checklist

- [ ] API keys stored in secrets manager (not .env)
- [ ] HTTPS enabled (SSL/TLS certificate)
- [ ] CORS properly configured for production origin
- [ ] Rate limiting enabled
- [ ] WebSocket authentication implemented
- [ ] Input validation on all endpoints
- [ ] Database passwords rotated regularly
- [ ] Logs don't contain sensitive data
- [ ] Network policies restrict traffic
- [ ] Regular security scanning (Snyk, Trivy)

## Rollback Procedure

```bash
# Kubernetes
kubectl rollout undo deployment/voice-ai-agent

# Docker Compose
docker-compose down
git checkout previous-version
docker-compose up -d --build

# ECS
aws ecs update-service \
  --cluster voice-ai \
  --service voice-ai-agent \
  --task-definition voice-ai-agent:previous-version
```

---

For local development, see [QUICKSTART.md](./QUICKSTART.md)
