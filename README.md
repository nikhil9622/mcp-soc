# MCP SOC - Multi-Tenant Security Operations Center

[![CI/CD](https://github.com/YOUR_ORG/mcp-soc/workflows/MCP%20SOC%20CI%2FCD%20Pipeline/badge.svg)](https://github.com/YOUR_ORG/mcp-soc/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A cloud-native, multi-tenant Security Operations Center built with **FastAPI**, **Redis Streams**, **MongoDB**, and **Claude AI**. Automates threat detection, correlation, investigation, and alerting using Sigma detection rules and MITRE ATT&CK mapping.

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.12+**
- **Docker & Docker Compose**
- **Git**

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_ORG/mcp-soc.git
cd mcp-soc

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

**Required API Keys:**
- `ANTHROPIC_API_KEY` - Claude AI for investigation summaries
- `SENDGRID_API_KEY` - Email delivery for alerts
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - S3 raw log storage

### 3. Start Services

```bash
# Start Redis & MongoDB with Docker
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 4. Run the Broker

```bash
# Start FastAPI broker
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit: **http://localhost:8000/docs** for interactive API documentation

### 5. Run Agents (ARQ Workers)

In separate terminals:

```bash
# Ingestion Agent
arq agents.ingestion.WorkerSettings

# Detection Agent
arq agents.detection.WorkerSettings

# Correlation Agent
arq agents.correlation.WorkerSettings

# Investigation Agent
arq agents.investigation.WorkerSettings

# Alerting Agent
arq agents.alerting.WorkerSettings
```

---

## 📋 Architecture

### Agent Pipeline

```
CloudTrail / Syslog Logs
         ↓
[Ingestion Agent] → Normalize → NormalizedEvent
         ↓ (Redis Stream: soc:events:{tenant_id})
[Detection Agent] → Sigma Rules → DetectionEvent
         ↓ (Redis Stream: soc:detections:{tenant_id})
[Correlation Agent] → NetworkX Graph → Incident
         ↓ (Redis Stream: soc:incidents:{tenant_id})
[Investigation Agent] → Claude AI → IncidentSummary
         ↓ (Redis Stream: soc:summaries:{tenant_id})
[Alerting Agent] → Email Delivery → Alert
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| **API** | FastAPI + Uvicorn |
| **Workers** | ARQ (async task queue) |
| **Event Bus** | Redis Streams |
| **Database** | MongoDB (Motor async driver) |
| **Storage** | AWS S3 (raw logs) |
| **Detection** | Sigma rules (YAML) |
| **Correlation** | NetworkX (graph-based) |
| **Investigation** | Anthropic Claude API |
| **Alerting** | SendGrid (email) |
| **Testing** | pytest + pytest-asyncio |
| **Linting** | Ruff |

---

## 🔧 Development

### Project Structure

```
mcp-soc/
├── agents/                 # 5 pipeline agents (Ingestion, Detection, etc.)
│   ├── ingestion.py
│   ├── detection.py
│   ├── correlation.py
│   ├── investigation.py
│   └── alerting.py
├── api/                    # FastAPI routes
│   ├── tenants.py
│   ├── logs.py
│   ├── incidents.py
│   └── feedback.py
├── config/                 # Configuration management
│   └── settings.py
├── db/                     # Database clients
│   ├── mongo.py
│   └── redis_client.py
├── detection_rules/        # Sigma detection rules (YAML)
│   ├── brute_force.yml
│   ├── privilege_escalation.yml
│   └── ...
├── shared/                 # Shared utilities
│   ├── models.py          # Pydantic schemas
│   ├── api_keys.py
│   └── mitre.py
├── tests/                  # Test suite (64+ tests)
│   ├── test_*.py
│   └── fixtures/
├── docker-compose.yml      # Local development services
├── Dockerfile              # Production container
├── main.py                 # FastAPI application entry
├── requirements.txt        # Python dependencies
└── .env.example            # Environment template
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_detection_rules.py -v

# Run with coverage
pytest tests/ --cov=agents --cov=shared --cov=api --cov-report=term-missing

# Run integration tests
pytest tests/ -m integration
```

### Linting

```bash
# Check code quality
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .
```

---

## 📚 API Endpoints

### Tenant Management

```http
POST /api/tenants/create
```
Create a new tenant and generate API key.

**Request:**
```json
{
  "email": "admin@example.com",
  "plan": "pro"
}
```

**Response:**
```json
{
  "user_id": "tenant_abc123",
  "api_key": "sk_live_...",
  "created_at": "2024-06-15T14:30:00Z"
}
```

### Log Ingestion

```http
POST /api/logs/ingest
Authorization: Bearer {api_key}
```

**Request:**
```json
{
  "logs": [
    {
      "eventName": "ConsoleLogin",
      "sourceIPAddress": "1.2.3.4",
      "userIdentity": {"userName": "alice"},
      "responseElements": {"ConsoleLogin": "Failure"}
    }
  ]
}
```

### Incident Retrieval

```http
GET /api/incidents?tenant_id=tenant_abc123&limit=50
Authorization: Bearer {api_key}
```

### Feedback Submission

```http
POST /api/feedback/{alert_id}
Authorization: Bearer {api_key}
```

**Request:**
```json
{
  "feedback": "tp",
  "note": "Confirmed brute force attack"
}
```

**Full API Docs:** Visit `/docs` after starting the broker.

---

## 🔐 Security

### Tenant Isolation

- All Redis Stream keys include `tenant_id`: `soc:events:{tenant_id}`
- All MongoDB queries filter by `tenant_id`
- S3 logs stored with tenant prefix: `s3://bucket/{tenant_id}/...`

### API Authentication

- API key per tenant (bcrypt hashed)
- Bearer token authentication
- Rate limiting per tenant

### Detection Rules

5 Sigma rules included:

1. **Brute Force Logins** - >5 failed logins in 10 minutes
2. **Login from New Geo** - IP geolocation change
3. **Privilege Escalation** - `AssumeRole` or root access
4. **Unusual Access Hours** - Login outside 9-17 business hours
5. **Root Account Usage** - Direct root account login

Add custom rules in `detection_rules/*.yml` following Sigma format.

---

## 🚢 Deployment

### Docker Deployment

```bash
# Build production image
docker build -t mcp-soc:latest .

# Run all services
docker-compose up -d

# Scale agents
docker-compose up -d --scale ingestion=3
```

### Environment Variables

Required in production:

```bash
REDIS_URL=redis://redis:6379
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB=mcp_soc
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=mcp-soc-logs
ANTHROPIC_API_KEY=sk-ant-...
SENDGRID_API_KEY=SG...
ALERT_FROM_EMAIL=alerts@your-domain.com
```

### Cloud Deployment

See [docs/deployment-guide.md](docs/deployment-guide.md) for:
- AWS deployment with ECS
- GCP deployment with Cloud Run
- Azure deployment with Container Apps
- Kubernetes manifests

---

## 📊 Monitoring

### Health Check

```http
GET /api/health
```

Returns service status:
```json
{
  "status": "healthy",
  "redis": "connected",
  "mongodb": "connected",
  "timestamp": "2024-06-15T14:30:00Z"
}
```

### Metrics

Monitor these key metrics:
- **Event throughput** - Events/second ingested
- **Detection latency** - Time from event to detection
- **False positive rate** - FP / Total alerts
- **Alert delivery time** - End-to-end pipeline latency
- **Redis Stream lag** - Consumer group lag
- **MongoDB query time** - Database performance

### Logging

Logs are structured JSON:

```json
{
  "timestamp": "2024-06-15T14:30:00Z",
  "level": "INFO",
  "agent": "detection",
  "tenant_id": "tenant_abc123",
  "message": "Detection matched",
  "rule_id": "brute_force",
  "event_id": "evt_123"
}
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and test: `pytest tests/ -v`
4. Lint code: `ruff check .`
5. Commit: `git commit -m "feat: add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

### Commit Convention

```
type(scope): description

Types: feat, fix, docs, refactor, test, chore
```

---

## 📖 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Development guide for AI assistants
- **[PROJECT_RULES.md](PROJECT_RULES.md)** - GSD methodology
- **[docs/runbook.md](docs/runbook.md)** - Operational procedures
- **[docs/deployment-guide.md](docs/deployment-guide.md)** - Cloud deployment
- **[API Docs](http://localhost:8000/docs)** - Interactive OpenAPI docs

---

## 📝 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- **Sigma HQ** - Detection rule format
- **MITRE ATT&CK** - Threat taxonomy
- **Anthropic** - Claude AI API
- **FastAPI** - Modern Python web framework
- **ARQ** - Async task queue

---

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/YOUR_ORG/mcp-soc/issues)
- **Discussions:** [GitHub Discussions](https://github.com/YOUR_ORG/mcp-soc/discussions)
- **Email:** support@your-domain.com

---

**Built with ❤️ for Security Teams**
