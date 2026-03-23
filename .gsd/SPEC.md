---
title: MCP SOC - Multi-tenant Security Operations Center
version: 1.0
status: FINALIZED
created: 2026-03-22
updated: 2026-03-22
---

# MCP SOC Specification

## Executive Summary

MCP SOC is a greenfield, cloud-based multi-tenant Security Operations Center that ingests AWS CloudTrail logs and syslog events, detects security anomalies using Sigma rules, correlates incidents using graph-based entity clustering, generates AI-powered incident summaries, and delivers alerts via email.

**Scope:** MVP only. No EDR, kernel monitoring, complex ML, or UI dashboard.

---

## Requirements

### REQ-01: Project Foundation
- [ ] Git repository initialized
- [ ] Python 3.11+ environment with pip
- [ ] All dependencies installed (FastAPI, motor, boto3, redis, pytest)
- [ ] Docker and Docker Compose for services (Redis, MongoDB, LocalStack)
- [ ] Configuration management (.env files)
- [ ] Linting and testing infrastructure (ruff, pytest-asyncio)

### REQ-02: Core Data Models
- [ ] NormalizedEvent schema (Pydantic v2)
- [ ] DetectionEvent schema
- [ ] Incident schema (with detection_ids, entities)
- [ ] IncidentSummary schema (with CLaude Structured Output fields)
- [ ] Alert schema (with feedback: tp|fp|null)
- [ ] MongoDB collections with required indexes
- [ ] Redis Stream consumer group setup

### REQ-03: Ingestion Agent
- [ ] AWS CloudTrail log ingestion
- [ ] CloudTrail → NormalizedEvent transformation
- [ ] Tenant isolation (every event tagged with tenant_id)
- [ ] Raw log storage in S3 with tenant_id prefix
- [ ] Event storage in MongoDB
- [ ] Publish NormalizedEvent to Redis stream `soc:events:{tenant_id}`
- [ ] Error handling and retry logic
- [ ] ARQ worker integration

### REQ-04: Detection Agent
- [ ] Sigma rule YAML format validation
- [ ] 5 Sigma detection rules deployed:
  - Rule 1: Brute force logins (>5 failed ConsoleLogin)
  - Rule 2: Login from new geo (IP location change)
  - Rule 3: Privilege escalation (AssumeRole patterns)
  - Rule 4: Unusual access hours (off-business-hours login)
  - Rule 5: Root account usage (direct root login)
- [ ] sigma-rule-matcher integration
- [ ] MITRE ATT&CK mapping (T-codes)
- [ ] Score calculation (0-100, inversely correlated with alert fatigue)
- [ ] Publish DetectionEvent to Redis stream `soc:detections:{tenant_id}`
- [ ] Deterministic only (zero LLM calls)
- [ ] ARQ worker integration

### REQ-05: Correlation Agent
- [ ] NetworkX graph construction (user nodes, IP nodes)
- [ ] 60-minute sliding window for entity clustering
- [ ] Detection grouping by user + IP pair
- [ ] Incident creation with detection_ids and entity list
- [ ] Tenant isolation
- [ ] Publish Incident to Redis stream `soc:incidents:{tenant_id}`
- [ ] Deterministic only (zero LLM calls)
- [ ] ARQ worker integration

### REQ-06: Investigation Agent
- [ ] Read Incident from Redis stream
- [ ] Call Claude API with Structured Output schema (IncidentSummary)
- [ ] System prompt: "Base analysis only on provided event data. Do not infer or assume."
- [ ] Output fields: summary, what_happened, why_suspicious, impact, recommended_action, severity
- [ ] Tenant isolation
- [ ] Publish IncidentSummary to Redis stream `soc:summaries:{tenant_id}`
- [ ] Error handling for API failures
- [ ] ARQ worker integration

### REQ-07: Alerting Agent
- [ ] Read IncidentSummary from Redis stream
- [ ] Email template rendering
- [ ] fastapi-mail integration
- [ ] Send alert email with severity, summary, and action
- [ ] Create Alert record in MongoDB with feedback endpoint reference
- [ ] Tenant isolation
- [ ] Deterministic only (zero LLM calls)
- [ ] ARQ worker integration

### REQ-08: Broker API (FastAPI)
- [ ] `/api/tenants/create` — on-board new tenant
- [ ] `/api/logs/ingest` — accept CloudTrail/syslog batches
- [ ] `/api/feedback/{alert_id}` — receive TP/FP feedback
- [ ] `/api/incidents?tenant_id=...` — list incidents
- [ ] `/api/health` — readiness probe
- [ ] Request authentication (API key per tenant)
- [ ] Rate limiting per tenant
- [ ] Request validation (Pydantic)

### REQ-09: Testing & Quality
- [ ] Unit tests for all agents (>80% coverage on critical paths)
- [ ] Integration tests with Docker Compose
- [ ] Synthetic test logs (SALO format)
- [ ] End-to-end workflow test (log → alert)
- [ ] All tests pass before commit
- [ ] Linting passes (ruff check .)

### REQ-10: Documentation & Deployment
- [ ] README.md with setup instructions
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Runbook for operational monitoring
- [ ] Docker images for all agents
- [ ] Docker Compose production configuration
- [ ] Environment variable documentation
- [ ] Deployment checklist

---

## Hard Rules (Non-Negotiable)

1. **LLM only in Investigation Agent**  
   Ingestion, Detection, Correlation, and Alerting must be deterministic — zero LLM calls elsewhere.

2. **Investigation Agent fires AFTER Correlation**  
   Never on raw detection events. LLM on every detection = budget destruction.

3. **Tenant isolation on every operation**  
   - Redis Stream keys: `soc:{stream}:{tenant_id}`
   - MongoDB queries: start with `{"tenant_id": tenant_id}`
   - S3 paths: `s3://{bucket}/{tenant_id}/...`

4. **Detection-as-code**  
   Rules live in `detection_rules/` as Sigma YAML files. No hardcoded detection logic in Python.

5. **No hallucination**  
   Investigation Agent system prompt must forbid inference. Use Claude native Structured Outputs (schema-enforced), not prompt engineering.

6. **5 quality rules before 50 noisy ones**  
   Alert fatigue is the #1 SOC killer. Every false positive trains analysts to ignore alerts.

7. **Build TP/FP feedback endpoint on day one**  
   Most valuable long-term data in the system, even if unused initially.

---

## Success Criteria

- ✅ All agents deployed and operational
- ✅ End-to-end log → alert pipeline working
- ✅ All tests pass
- ✅ Code linted (ruff)
- ✅ Feedback endpoint operational
- ✅ Documentation complete
- ✅ Deployable via Docker Compose

---

## Out of Scope (Explicitly Not Building)

- ❌ Full EDR or kernel monitoring
- ❌ Complex ML pipelines or anomaly detection
- ❌ Per-tenant MongoDB databases (use tenant_id field)
- ❌ Kafka (Redis Streams handles MVP scale)
- ❌ UI/dashboard (pipeline must be tested first)
- ❌ Multi-region failover
- ❌ Advanced correlation (entity behavior analysis, kill-chain detection)

---

## Tech Stack (Immutable for MVP)

| Concern | Technology | Rationale |
|---------|-----------|-----------|
| API / Broker | FastAPI + ARQ | Native async, Redis-based task queue |
| Event bus | Redis Streams | Persistent, ACK, consumer groups — NOT pub/sub |
| Databases | MongoDB (motor) + S3 (boto3) | Async MongoDB, S3 for raw logs |
| Detection rules | Sigma (YAML) | Industry standard, evaluated with sigma-rule-matcher |
| ATT&CK mapping | mitreattack-python | MITRE framework integration |
| Correlation | NetworkX | Graph-based entity clustering |
| LLM | Anthropic Claude API | Investigation Agent only, Structured Outputs |
| Schema validation | Pydantic v2 | Strict typing everywhere |
| Email | fastapi-mail | MVP alerting |
| Linting | Ruff | Fast, minimal config |
| Testing | pytest + pytest-asyncio | Standard Python testing |

---

## Definitions

**NormalizedEvent:** Raw log transformed to common schema (tenant_id, timestamp, source, user, ip, action, metadata)

**DetectionEvent:** Sigma rule match with severity, MITRE technique, and score

**Incident:** Correlated group of detections by user+IP pair within 60-minute window

**IncidentSummary:** Claude-generated structured narrative (what happened, why suspicious, impact, action)

**Alert:** Email notification with feedback mechanism (true positive, false positive, null)

---

## Assumptions

1. AWS credentials available for CloudTrail ingestion
2. Email service (SMTP or AWS SES) available for alerting
3. Redis and MongoDB available (local Docker for dev, managed services for prod)
4. Anthropic Claude API key configured
5. Logs arrive in standard CloudTrail or syslog format
6. Deployment environment is cloud-native (AWS, GCP, Azure, or on-prem Kubernetes)

---

## Sign-Off

| Role | Name | Date | Notes |
|------|------|------|-------|
| Architect | — | 2026-03-22 | MVP scope locked |
| TBD | — | — | Pending approval |

---

**Status: FINALIZED** ✅  
Ready for ROADMAP and implementation phases.
