# Deployment Guide

This directory contains deployment configurations for multiple platforms.

## 🚀 Deployment Options

### 1. **Docker Compose (Local Development)**
```bash
docker-compose up --build
```
- Easiest for local testing
- Includes FastAPI + Redis
- Single command startup

### 2. **Docker Hub & Heroku**
Automated via GitHub Actions (.github/workflows/deploy-heroku.yml)

**Prerequisites:**
```bash
# Set GitHub Secrets
- HEROKU_API_KEY
- HEROKU_APP_NAME
- HEROKU_EMAIL
```

**Deploy:**
```bash
git push origin main  # Automatically deploys to Heroku
```

### 3. **Kubernetes (Production)**
```bash
# Update secrets
kubectl create secret generic llm-secrets \
  --from-literal=anthropic-key=$ANTHROPIC_API_KEY \
  --from-literal=openai-key=$OPENAI_API_KEY

# Deploy Redis
kubectl apply -f k8s-redis.yaml

# Deploy Application
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl get pods
kubectl get svc
```

**Access:**
```bash
kubectl port-forward svc/voice-ai-agent-svc 8000:80
# Visit http://localhost:8000/docs
```

### 4. **AWS ECS (Production)**

**Setup:**
```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name voice-ai-cluster

# Create log group
aws logs create-log-group --log-group-name /ecs/voice-ai-agent

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json

# Create service
aws ecs create-service \
  --cluster voice-ai-cluster \
  --service-name voice-ai-agent-service \
  --task-definition voice-ai-agent \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

**Deploy updates:**
```bash
git push origin main  # Automatically builds and deploys
```

### 5. **Google Cloud Run**
```bash
gcloud run deploy voice-ai-agent \
  --source voice-ai-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY,REDIS_URL=$REDIS_URL"
```

### 6. **Azure Container Instances**
```bash
az container create \
  --resource-group mygroup \
  --name voice-ai-agent \
  --image AJAY-4B2/voice-ai-agent:latest \
  --cpu 2 --memory 2 \
  --environment-variables \
    ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    OPENAI_API_KEY=$OPENAI_API_KEY \
    REDIS_URL=$REDIS_URL \
  --ports 8000
```

## 🔐 Secrets Management

### GitHub Actions Secrets
Set these in your GitHub repository settings (Settings > Secrets and variables > Actions):

```
DOCKER_USERNAME      # Docker Hub username
DOCKER_PASSWORD      # Docker Hub token
AWS_ACCESS_KEY_ID    # AWS credentials
AWS_SECRET_ACCESS_KEY
HEROKU_API_KEY       # Heroku deployment token
HEROKU_APP_NAME      # Your Heroku app name
HEROKU_EMAIL         # Heroku account email
```

### Environment Variables for Deployment

**Production:**
```env
APP_ENV=production
LOG_LEVEL=INFO
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
REDIS_URL=redis://your-redis-host:6379
```

## 📊 Deployment Status

### Kubernetes
```bash
# Check pods
kubectl get pods -l app=voice-ai-agent

# View logs
kubectl logs -l app=voice-ai-agent -f

# Scale deployment
kubectl scale deployment voice-ai-agent --replicas=5

# Check metrics
kubectl top pods
```

### AWS ECS
```bash
# List services
aws ecs list-services --cluster voice-ai-cluster

# View task status
aws ecs list-tasks --cluster voice-ai-cluster --service-name voice-ai-agent-service

# Check logs
aws logs tail /ecs/voice-ai-agent --follow
```

## 🔄 CI/CD Pipelines

### Workflows configured:

1. **tests.yml** - Run tests on every push
2. **docker.yml** - Build Docker image (deprecated, use build-docker.yml)
3. **build-docker.yml** - Build and push to Docker Hub
4. **deploy-heroku.yml** - Auto-deploy to Heroku
5. **deploy-aws.yml** - Build and deploy to AWS ECS

### Trigger deployments:
```bash
git push origin main       # Triggers all workflows
git tag v1.0.0
git push origin v1.0.0     # Triggers versioned build
```

## 🚨 Troubleshooting

### Kubernetes issues
```bash
# Check pod status
kubectl describe pod <pod-name>

# View pod logs
kubectl logs <pod-name>

# Port forward for debugging
kubectl port-forward pod/<pod-name> 8000:8000
```

### ECS issues
```bash
# Check task status
aws ecs describe-tasks \
  --cluster voice-ai-cluster \
  --tasks <task-arn>

# View logs
aws logs tail /ecs/voice-ai-agent --follow
```

### Docker issues
```bash
# Build locally
docker build -t voice-ai-agent voice-ai-agent/

# Run locally
docker run -p 8000:8000 voice-ai-agent

# Push to registry
docker tag voice-ai-agent AJAY-4B2/voice-ai-agent:latest
docker push AJAY-4B2/voice-ai-agent:latest
```

## 📚 Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Heroku Documentation](https://devcenter.heroku.com/)
- [Docker Documentation](https://docs.docker.com/)

---

For more information, see [DEPLOYMENT.md](../DEPLOYMENT.md)
