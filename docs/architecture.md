# MCP SOC Architecture Documentation

**Version:** 1.0  
**Last Updated:** 2026-03-22  
**Document Type:** Technical Architecture

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MCP SOC ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  External        │
│  Log Sources     │
│  ─────────────   │
│  • CloudTrail    │──┐
│  • Syslog        │  │
│  • App Logs      │  │
└──────────────────┘  │
                      │ HTTPS POST
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Broker (Port 8000)                                     │   │
│  │  ────────────────────────────────────────────────────────       │   │
│  │  • POST /api/tenants/create     - Create tenant                 │   │
│  │  • POST /api/logs/ingest        - Ingest logs                   │   │
│  │  • GET  /api/incidents          - List incidents                │   │
│  │  • POST /api/feedback/{alert}   - Submit feedback (TP/FP)       │   │
│  │  • GET  /api/health             - Health check                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                              │
│           │ Authentication (Bearer Token)                                │
│           │ Rate Limiting (per tenant)                                   │
│           ▼                                                              │
└─────────────────────────────────────────────────────────────────────────┘
           │
           │ Enqueue to Redis Streams
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT PIPELINE                                    │
│                                                                          │
│  ┌────────────────────┐                                                 │
│  │ INGESTION AGENT    │  Normalize events                               │
│  │ (ARQ Worker)       │  Extract: user, ip, action, timestamp          │
│  └──────┬─────────────┘  Store raw logs → S3                           │
│         │ Publish → Redis Stream: soc:events:{tenant_id}               │
│         ▼                                                                │
│  ┌────────────────────┐                                                 │
│  │ DETECTION AGENT    │  Apply Sigma rules                             │
│  │ (ARQ Worker)       │  Map to MITRE ATT&CK                           │
│  └──────┬─────────────┘  Calculate risk score                          │
│         │ Publish → Redis Stream: soc:detections:{tenant_id}           │
│         ▼                                                                │
│  ┌────────────────────┐                                                 │
│  │ CORRELATION AGENT  │  Build NetworkX graph (user+IP nodes)          │
│  │ (ARQ Worker)       │  Cluster detections (60-min window)            │
│  └──────┬─────────────┘  Create incidents                              │
│         │ Publish → Redis Stream: soc:incidents:{tenant_id}            │
│         ▼                                                                │
│  ┌────────────────────┐                                                 │
│  │ INVESTIGATION      │  Call Claude API                                │
│  │ AGENT (ARQ Worker) │  Generate incident summary                      │
│  └──────┬─────────────┘  Structured output (no hallucination)          │
│         │ Publish → Redis Stream: soc:summaries:{tenant_id}            │
│         ▼                                                                │
│  ┌────────────────────┐                                                 │
│  │ ALERTING AGENT     │  Send email via SendGrid                        │
│  │ (ARQ Worker)       │  Create alert record                            │
│  └────────────────────┘  Capture TP/FP feedback                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
           │
           │ Data Storage & Retrieval
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                        │
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │   REDIS      │   │  MONGODB     │   │   AWS S3     │               │
│  │  (Streams)   │   │  (Events)    │   │ (Raw Logs)   │               │
│  │              │   │              │   │              │               │
│  │ • Events     │   │ • events     │   │ • CloudTrail │               │
│  │ • Detections │   │ • detections │   │ • Syslog     │               │
│  │ • Incidents  │   │ • incidents  │   │ • App logs   │               │
│  │ • Summaries  │   │ • alerts     │   │              │               │
│  │ • Feedback   │   │ • users      │   │ Organized    │               │
│  │              │   │ • audit_log  │   │ by tenant_id │               │
│  └──────────────┘   └──────────────┘   └──────────────┘               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
CloudTrail Event → Ingestion Agent
                        │
                        ├─→ S3 (raw log storage)
                        │
                        ├─→ MongoDB events collection
                        │
                        └─→ Redis Stream: soc:events:{tenant_id}
                                  │
                                  ▼
                          Detection Agent
                        (Sigma rule evaluation)
                                  │
                                  ├─→ MongoDB detections collection
                                  │
                                  └─→ Redis Stream: soc:detections:{tenant_id}
                                            │
                                            ▼
                                  Correlation Agent
                              (NetworkX graph clustering)
                                            │
                                            ├─→ MongoDB incidents collection
                                            │
                                            └─→ Redis Stream: soc:incidents:{tenant_id}
                                                      │
                                                      ▼
                                            Investigation Agent
                                          (Claude AI summarization)
                                                      │
                                                      ├─→ MongoDB (update incident)
                                                      │
                                                      └─→ Redis Stream: soc:summaries:{tenant_id}
                                                                │
                                                                ▼
                                                      Alerting Agent
                                                    (Email via SendGrid)
                                                                │
                                                                ├─→ MongoDB alerts collection
                                                                │
                                                                └─→ Email to SOC analyst
                                                                          │
                                                                          ▼
                                                                    Analyst Feedback
                                                                  (TP/FP via API)
                                                                          │
                                                                          └─→ Redis Stream: soc:feedback:{tenant_id}
```

---

## Component Breakdown

### 1. FastAPI Broker

**Responsibilities:**
- HTTP API endpoints
- Authentication (API key validation)
- Rate limiting (per tenant)
- Request validation (Pydantic schemas)
- Job enqueueing (Redis Streams)

**Technology:**
- FastAPI 0.115+
- Uvicorn (ASGI server)
- Pydantic v2 (validation)

**Scaling:** Horizontal (stateless, 2-10 instances)

---

### 2. Ingestion Agent

**Responsibilities:**
- Parse CloudTrail/Syslog JSON
- Normalize to `NormalizedEvent` schema
- Extract: user, IP, action, timestamp, metadata
- Store raw logs in S3 (tenant prefix)
- Store normalized events in MongoDB
- Publish to Redis Stream

**Technology:**
- ARQ (async worker)
- boto3 (S3 client)
- motor (MongoDB async)

**Scaling:** Horizontal based on stream lag

---

### 3. Detection Agent

**Responsibilities:**
- Read from `soc:events:{tenant_id}`
- Apply 5 Sigma detection rules (YAML)
- Map to MITRE ATT&CK technique IDs
- Calculate risk score (0-100)
- Create `DetectionEvent` records
- Publish to Redis Stream

**Technology:**
- pySigma (rule engine)
- mitreattack-python (ATT&CK mapping)

**Scaling:** Horizontal based on CPU

---

### 4. Correlation Agent

**Responsibilities:**
- Read from `soc:detections:{tenant_id}`
- Build NetworkX graph (user nodes, IP nodes)
- Cluster detections within 60-minute window
- Group related detections into `Incident`
- Calculate combined severity
- Publish to Redis Stream

**Technology:**
- NetworkX (graph library)

**Scaling:** Vertical (single instance per tenant)

---

### 5. Investigation Agent

**Responsibilities:**
- Read from `soc:incidents:{tenant_id}`
- Call Claude API with incident context
- Generate `IncidentSummary` (structured output)
- Fields: summary, what_happened, why_suspicious, impact, recommended_action
- No hallucination (data-only analysis)
- Publish to Redis Stream

**Technology:**
- Anthropic Claude API
- Claude Structured Outputs

**Scaling:** Horizontal based on API quota

---

### 6. Alerting Agent

**Responsibilities:**
- Read from `soc:summaries:{tenant_id}`
- Render email template (Jinja2)
- Send via SendGrid
- Create `Alert` record in MongoDB
- Include feedback links (TP/FP)
- Publish feedback to stream

**Technology:**
- SendGrid (email delivery)
- Jinja2 (templates)

**Scaling:** Horizontal based on queue length

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **API** | FastAPI | 0.115+ | REST endpoints |
| **Workers** | ARQ | 0.26+ | Async task queue |
| **Event Bus** | Redis Streams | 7+ | Inter-agent messaging |
| **Database** | MongoDB | 7+ | Event/incident storage |
| **Storage** | AWS S3 | - | Raw log archival |
| **Detection** | pySigma | 0.11+ | Sigma rule engine |
| **Graph** | NetworkX | 3.3+ | Correlation clustering |
| **AI** | Anthropic Claude | - | Incident investigation |
| **Email** | SendGrid | 6.11+ | Alert delivery |
| **Schema** | Pydantic | 2.8+ | Data validation |
| **Testing** | pytest | 8.3+ | Test framework |
| **Linting** | Ruff | 0.6+ | Code quality |

---

## Security Architecture

### Tenant Isolation

```
┌─────────────────────────────────────────┐
│  TENANT ISOLATION LAYERS                │
└─────────────────────────────────────────┘

1. API Layer:
   ✓ API key → tenant_id mapping
   ✓ All requests scoped to tenant_id
   ✓ Rate limiting per tenant

2. Redis Streams:
   ✓ Stream keys: soc:{stream}:{tenant_id}
   ✓ Consumer groups per tenant
   ✓ No cross-tenant access

3. MongoDB:
   ✓ Every query filters by tenant_id
   ✓ Compound indexes (tenant_id, ...)
   ✓ audit_log is append-only

4. S3 Storage:
   ✓ Prefix: s3://{bucket}/{tenant_id}/...
   ✓ IAM policies per tenant (optional)
   ✓ Encryption at rest
```

### Authentication Flow

```
Client Request
    │
    ├─→ Extract Bearer token
    │
    ├─→ Query users collection
    │   (api_key_prefix match)
    │
    ├─→ Verify bcrypt hash
    │
    ├─→ Extract tenant_id
    │
    └─→ Attach to request context
         │
         └─→ All downstream operations
             use this tenant_id
```

---

## Monitoring & Observability

### Key Metrics

```python
# Event throughput (events/sec)
metric: "soc.events.ingested"
threshold: 100/sec (alert if < 10/sec)

# Detection latency (time from event to detection)
metric: "soc.detection.latency"
threshold: < 5 seconds

# False positive rate
metric: "soc.alerts.fp_rate"
threshold: < 20%

# Alert delivery time (end-to-end)
metric: "soc.alert.delivery_time"
threshold: < 60 seconds

# Redis stream lag
metric: "redis.stream.lag"
threshold: < 1000 messages

# MongoDB query time
metric: "mongodb.query.duration"
threshold: < 100ms
```

### Health Checks

```
/api/health → Returns:
{
  "status": "healthy",
  "redis": "connected",
  "mongodb": "connected",
  "timestamp": "2024-06-15T14:30:00Z",
  "version": "1.0.0"
}
```

---

## Deployment Architectures

### Small Deployment (< 1K events/hour)

```
Single Server:
  - 1x Broker (512 MB)
  - 1x each Agent (256 MB)
  - Redis (single instance)
  - MongoDB (single instance)

Total: ~2 GB RAM, 2 vCPU
Cost: ~$50-100/month
```

### Medium Deployment (< 10K events/hour)

```
Multi-Server:
  - 2x Broker (1 GB each)
  - 2x Ingestion, Detection (512 MB each)
  - 1x Correlation, Investigation, Alerting
  - Redis Cluster (3 nodes)
  - MongoDB Replica Set (3 nodes)

Total: ~8 GB RAM, 6 vCPU
Cost: ~$300-500/month
```

### Large Deployment (> 100K events/hour)

```
Kubernetes Cluster:
  - 5x Broker (2 GB each, HPA)
  - 10x Ingestion, 8x Detection (HPA)
  - 3x Correlation, Investigation, Alerting
  - Redis Cluster (6 nodes, multi-AZ)
  - MongoDB Sharded Cluster

Total: ~50+ GB RAM, 30+ vCPU
Cost: ~$2000-5000/month
```

---

## Troubleshooting Flowchart

```
┌─────────────────────────┐
│  Issue Reported         │
└───────────┬─────────────┘
            │
            ▼
     ┌─────────────┐
     │ Check Logs  │
     └──────┬──────┘
            │
     ┌──────▼──────────────────────────┐
     │  Error Type?                    │
     └──┬──────┬──────┬──────┬─────────┘
        │      │      │      │
   ┌────▼──┐ ┌─▼───┐ ┌─▼──┐ ┌▼────┐
   │ 500   │ │ 401 │ │4XX │ │Slow │
   │ Error │ │Auth │ │Bad │ │Perf │
   └───┬───┘ └──┬──┘ └─┬──┘ └──┬──┘
       │        │      │       │
   ┌───▼───┐ ┌──▼──┐ ┌─▼───┐ ┌▼─────┐
   │Check  │ │Check│ │Val  │ │Check │
   │Stack  │ │Keys │ │Err  │ │Redis │
   │Trace  │ │     │ │     │ │Lag   │
   └───┬───┘ └──┬──┘ └─┬───┘ └──┬───┘
       │        │      │        │
   ┌───▼────────▼──────▼────────▼───┐
   │   Apply Fix & Monitor          │
   └────────────────────────────────┘
```

---

## Appendix: Detection Rules

### Sigma Rule Example

```yaml
# detection_rules/brute_force.yml
title: Multiple Failed Login Attempts
id: bf-001
status: stable
description: Detects brute force attacks (>5 failed logins in 10 minutes)
logsource:
  product: cloudtrail
  service: signin
detection:
  selection:
    eventName: ConsoleLogin
    responseElements.ConsoleLogin: Failure
  condition: selection
  timeframe: 10m
  count: 5
falsepositives:
  - User forgot password
level: high
tags:
  - attack.t1110
  - attack.credential_access
```

---

**Document Version:** 1.0  
**Architecture Review:** Quarterly  
**Last Updated:** 2026-03-22  
**Maintained By:** Platform Engineering Team
