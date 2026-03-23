# MCP SOC Deployment Guide

**Version:** 1.0  
**Target Platforms:** AWS, GCP, Azure, On-Premises  
**Container Orchestration:** Docker Compose, Kubernetes, ECS

---

## Table of Contents

1. [Deployment Options](#deployment-options)
2. [Prerequisites](#prerequisites)
3. [Docker Compose (Local/Single Server)](#docker-compose-deployment)
4. [AWS Deployment](#aws-deployment-ecs)
5. [GCP Deployment](#gcp-deployment-cloud-run)
6. [Azure Deployment](#azure-deployment-container-apps)
7. [Kubernetes Deployment](#kubernetes-deployment)
8. [Production Checklist](#production-checklist)
9. [Security Hardening](#security-hardening)
10. [Scaling Strategy](#scaling-strategy)

---

## Deployment Options

| Option | Best For | Complexity | Cost |
|--------|----------|------------|------|
| **Docker Compose** | Development, small deployments | Low | $ |
| **AWS ECS** | AWS-native, scalable | Medium | $$ |
| **GCP Cloud Run** | Serverless, auto-scaling | Low | $$ |
| **Azure Container Apps** | Azure-native | Medium | $$ |
| **Kubernetes** | Multi-cloud, enterprise | High | $$$ |

---

## Prerequisites

### Required Services

- **Redis** (or Redis-compatible service)
  - AWS ElastiCache, GCP Memorystore, Azure Cache for Redis
- **MongoDB** (or MongoDB Atlas)
  - MongoDB Atlas (recommended for production)
- **S3-compatible storage**
  - AWS S3, GCP Cloud Storage, Azure Blob Storage
- **Email service**
  - SendGrid, AWS SES, Postmark

### Required Credentials

```bash
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Email Service (SendGrid)
SENDGRID_API_KEY=SG...

# AWS (for S3)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Firebase (for authentication)
FIREBASE_SERVICE_ACCOUNT_PATH=./config/firebase-service-account.json
```

---

## Docker Compose Deployment

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_ORG/mcp-soc.git
cd mcp-soc
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with production values
```

**Minimum required:**
```bash
REDIS_URL=redis://redis:6379
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB=mcp_soc
ANTHROPIC_API_KEY=sk-ant-...
SENDGRID_API_KEY=SG...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=mcp-soc-logs
```

### 3. Deploy Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Verify Deployment

```bash
# Health check
curl http://localhost:8000/api/health

# Expected response:
{
  "status": "healthy",
  "redis": "connected",
  "mongodb": "connected"
}
```

### 5. Scale Agents

```bash
# Scale based on load
docker-compose up -d --scale agent-ingestion=3 --scale agent-detection=2
```

---

## AWS Deployment (ECS)

### Architecture

```
Internet → ALB → ECS Tasks
                 ├── Broker (Fargate)
                 ├── Ingestion Agent (Fargate)
                 ├── Detection Agent (Fargate)
                 ├── Correlation Agent (Fargate)
                 ├── Investigation Agent (Fargate)
                 └── Alerting Agent (Fargate)
                      ↓
        ┌──────────────┬──────────────┬──────────────┐
   ElastiCache     DocumentDB        S3
    (Redis)        (MongoDB)      (Logs)
```

### 1. Infrastructure Setup

**Using Terraform:**

```hcl
# terraform/main.tf

# VPC and Networking
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "mcp-soc-vpc"
  cidr = "10.0.0.0/16"
  
  azs             = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  
  enable_nat_gateway = true
  enable_dns_hostnames = true
}

# ElastiCache (Redis)
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "mcp-soc-redis"
  engine               = "redis"
  node_type            = "cache.t3.medium"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]
}

# DocumentDB (MongoDB-compatible)
resource "aws_docdb_cluster" "mongodb" {
  cluster_identifier      = "mcp-soc-mongodb"
  engine                  = "docdb"
  master_username         = "admin"
  master_password         = var.mongodb_password
  backup_retention_period = 7
  preferred_backup_window = "03:00-05:00"
  skip_final_snapshot     = false
  vpc_security_group_ids  = [aws_security_group.mongodb.id]
  db_subnet_group_name    = aws_docdb_subnet_group.mongodb.name
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "mcp-soc-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECR Repository
resource "aws_ecr_repository" "mcp_soc" {
  name                 = "mcp-soc"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "mcp-soc-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

# ECS Task Definition - Broker
resource "aws_ecs_task_definition" "broker" {
  family                   = "mcp-soc-broker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  
  container_definitions = jsonencode([{
    name  = "broker"
    image = "${aws_ecr_repository.mcp_soc.repository_url}:latest"
    
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    
    environment = [
      {name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379"},
      {name = "MONGODB_URL", value = "mongodb://${aws_docdb_cluster.mongodb.endpoint}:27017"},
      {name = "MONGODB_DB", value = "mcp_soc"},
      {name = "AWS_REGION", value = var.aws_region},
      {name = "S3_BUCKET", value = aws_s3_bucket.logs.id}
    ]
    
    secrets = [
      {name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic.arn},
      {name = "SENDGRID_API_KEY", valueFrom = aws_secretsmanager_secret.sendgrid.arn}
    ]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/mcp-soc-broker"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
    
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# ECS Service - Broker
resource "aws_ecs_service" "broker" {
  name            = "mcp-soc-broker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.broker.arn
  desired_count   = 2
  launch_type     = "FARGATE"
  
  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.broker.id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.broker.arn
    container_name   = "broker"
    container_port   = 8000
  }
  
  depends_on = [aws_lb_listener.broker]
}
```

### 2. Build and Push Images

```bash
# Build image
docker build -t mcp-soc:latest .

# Tag for ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

docker tag mcp-soc:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/mcp-soc:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/mcp-soc:latest
```

### 3. Deploy with Terraform

```bash
cd terraform/
terraform init
terraform plan
terraform apply
```

### 4. Configure Auto-Scaling

```hcl
# Auto-scaling for broker
resource "aws_appautoscaling_target" "broker" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.broker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "broker_cpu" {
  name               = "mcp-soc-broker-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.broker.resource_id
  scalable_dimension = aws_appautoscaling_target.broker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.broker.service_namespace
  
  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

---

## GCP Deployment (Cloud Run)

### 1. Build and Push to GCR

```bash
# Authenticate
gcloud auth configure-docker

# Build
docker build -t gcr.io/PROJECT_ID/mcp-soc:latest .

# Push
docker push gcr.io/PROJECT_ID/mcp-soc:latest
```

### 2. Deploy Services

```bash
# Deploy Broker
gcloud run deploy mcp-soc-broker \
  --image gcr.io/PROJECT_ID/mcp-soc:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars REDIS_URL=redis://REDIS_IP:6379 \
  --set-env-vars MONGODB_URL=mongodb://MONGODB_IP:27017 \
  --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest \
  --set-secrets SENDGRID_API_KEY=sendgrid-key:latest \
  --cpu 2 \
  --memory 2Gi \
  --min-instances 1 \
  --max-instances 10

# Deploy Ingestion Agent
gcloud run deploy mcp-soc-ingestion \
  --image gcr.io/PROJECT_ID/mcp-soc:latest \
  --platform managed \
  --region us-central1 \
  --no-allow-unauthenticated \
  --command "python,-m,arq,agents.ingestion.WorkerSettings" \
  --cpu 1 \
  --memory 1Gi \
  --min-instances 1
```

### 3. Setup Memorystore (Redis) and Cloud SQL

```bash
# Create Redis instance
gcloud redis instances create mcp-soc-redis \
  --size=5 \
  --region=us-central1 \
  --redis-version=redis_7_0

# Create MongoDB (via MongoDB Atlas or self-hosted)
```

---

## Kubernetes Deployment

### 1. Create Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mcp-soc
```

### 2. Deploy Redis and MongoDB

```yaml
# k8s/redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: mcp-soc
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: mcp-soc
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### 3. Deploy Broker

```yaml
# k8s/broker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-soc-broker
  namespace: mcp-soc
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-soc-broker
  template:
    metadata:
      labels:
        app: mcp-soc-broker
    spec:
      containers:
      - name: broker
        image: YOUR_REGISTRY/mcp-soc:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis:6379"
        - name: MONGODB_URL
          value: "mongodb://mongodb:27017"
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: mcp-soc-secrets
              key: anthropic-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
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
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-soc-broker
  namespace: mcp-soc
spec:
  type: LoadBalancer
  selector:
    app: mcp-soc-broker
  ports:
  - port: 80
    targetPort: 8000
```

### 4. Deploy Agents

```yaml
# k8s/agents-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-ingestion
  namespace: mcp-soc
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agent-ingestion
  template:
    metadata:
      labels:
        app: agent-ingestion
    spec:
      containers:
      - name: ingestion
        image: YOUR_REGISTRY/mcp-soc:latest
        command: ["python", "-m", "arq", "agents.ingestion.WorkerSettings"]
        env:
        - name: REDIS_URL
          value: "redis://redis:6379"
        - name: MONGODB_URL
          value: "mongodb://mongodb:27017"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### 5. Apply Manifests

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/mongodb-deployment.yaml
kubectl apply -f k8s/broker-deployment.yaml
kubectl apply -f k8s/agents-deployment.yaml

# Check status
kubectl get pods -n mcp-soc
kubectl logs -f deployment/mcp-soc-broker -n mcp-soc
```

---

## Production Checklist

### Before Deployment

- [ ] All environment variables configured
- [ ] API keys stored in secrets manager
- [ ] Database backups enabled
- [ ] Redis persistence enabled (AOF)
- [ ] SSL/TLS certificates configured
- [ ] Firewall rules configured
- [ ] Monitoring and alerting set up
- [ ] Log aggregation configured
- [ ] Load testing completed
- [ ] Security scan passed
- [ ] Documentation reviewed

### After Deployment

- [ ] Health checks passing
- [ ] All agents processing events
- [ ] Database connections stable
- [ ] Metrics flowing to monitoring
- [ ] Logs visible in aggregation tool
- [ ] Alerts configured and tested
- [ ] DNS configured
- [ ] Backups verified
- [ ] Runbook validated
- [ ] Team trained

---

## Security Hardening

### 1. Network Security

```bash
# AWS Security Group - Only allow HTTPS
ingress {
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}

# Deny direct database access from internet
egress {
  from_port   = 6379
  to_port     = 6379
  protocol    = "tcp"
  cidr_blocks = ["10.0.0.0/16"]  # VPC only
}
```

### 2. Secrets Management

```bash
# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
  --name mcp-soc/anthropic-key \
  --secret-string "sk-ant-..."

# Reference in ECS task definition
"secrets": [
  {
    "name": "ANTHROPIC_API_KEY",
    "valueFrom": "arn:aws:secretsmanager:region:account:secret:mcp-soc/anthropic-key"
  }
]
```

### 3. Container Security

```bash
# Run as non-root user (already in Dockerfile)
USER mcpsoc

# Read-only root filesystem
"readonlyRootFilesystem": true

# Drop all capabilities
"linuxParameters": {
  "capabilities": {
    "drop": ["ALL"]
  }
}
```

---

## Scaling Strategy

### Horizontal Scaling

| Component | Metric | Target | Min | Max |
|-----------|--------|--------|-----|-----|
| Broker | CPU Usage | 70% | 2 | 10 |
| Ingestion | Stream Lag | 1000 msgs | 1 | 5 |
| Detection | CPU Usage | 80% | 2 | 8 |
| Correlation | Queue Length | 500 | 1 | 3 |
| Investigation | API Latency | 5s | 1 | 5 |
| Alerting | Queue Length | 100 | 1 | 3 |

### Vertical Scaling

**Development:**
- Broker: 512 MB, 0.25 vCPU
- Agents: 256 MB, 0.25 vCPU

**Production:**
- Broker: 2 GB, 1 vCPU
- Agents: 1 GB, 0.5 vCPU

**Enterprise:**
- Broker: 4 GB, 2 vCPU
- Agents: 2 GB, 1 vCPU

---

## Monitoring Integration

### CloudWatch (AWS)

```python
# Log to CloudWatch
import watchtower
import logging

logger = logging.getLogger(__name__)
logger.addHandler(watchtower.CloudWatchLogHandler())
```

### Datadog

```bash
# Add Datadog agent sidecar
DD_API_KEY=... DD_SITE=datadoghq.com docker-compose up -d
```

### Prometheus + Grafana

```yaml
# Add metrics endpoint
@app.get("/metrics")
async def metrics():
    return prometheus_metrics()
```

---

**Document Owner:** Platform Team  
**Last Updated:** 2026-03-22  
**Next Review:** Quarterly
