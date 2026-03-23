---
milestone: MCP SOC MVP
version: 1.0.0
updated: 2026-03-22
---

# Roadmap — MCP SOC Multi-Tenant Security Operations Center

> **Current Phase:** 1 - Project Foundation  
> **Status:** Planning  
> **Spec Status:** ✅ FINALIZED

---

## Must-Haves (from SPEC.md)

- [x] Specification FINALIZED
- [ ] All 10 phases planned
- [ ] Project foundation (dependencies, config, CI/CD)
- [ ] Core data models (NormalizedEvent, DetectionEvent, Incident, IncidentSummary, Alert)
- [ ] 5 agents deployed (Ingestion, Detection, Correlation, Investigation, Alerting)
- [ ] FastAPI Broker with 5 REST endpoints
- [ ] TP/FP feedback endpoint
- [ ] End-to-end test (log → alert)
- [ ] Documentation and Docker deployment

---

## Phases

### Phase 1: Project Foundation & Infrastructure
**Status:** ⬜ Not Started  
**Objective:** Set up development environment, dependencies, config, Docker services, CI/CD skeleton  
**Requirements:** REQ-01, REQ-02 (partial)  
**Depends on:** None  
**Duration:** 1-2 days

**Deliverables:**
- Python environment (3.11+, venv/poetry)
- All production + dev dependencies installed
- Docker Compose with Redis, MongoDB, LocalStack
- `.env.example` with all config variables
- Ruff linting configured and passing
- GitHub Actions workflow (lint + test on PR)
- Project structure validated
- README with development setup instructions

**Plans:**
- [ ] Plan 1.1: Install dependencies and validate Python environment
- [ ] Plan 1.2: Set up Docker Compose (Redis, MongoDB, LocalStack)
- [ ] Plan 1.3: Configure environment variables and .env management
- [ ] Plan 1.4: Set up ruff linting and GitHub Actions
- [ ] Plan 1.5: Validate project structure and folder layout

**Acceptance Criteria:**
- `pip install -r requirements.txt` succeeds
- `docker-compose up -d` brings up all services
- `ruff check .` returns no errors
- GitHub Actions runs on commit (green check)

---

### Phase 2: Core Data Models & Database Schema
**Status:** ⬜ Not Started  
**Objective:** Define all Pydantic schemas, MongoDB collections with indexes, Redis Stream consumer groups  
**Requirements:** REQ-02  
**Depends on:** Phase 1  
**Duration:** 1 day

**Deliverables:**
- Pydantic v2 models (NormalizedEvent, DetectionEvent, Incident, IncidentSummary, Alert)
- MongoDB collection definitions and compound indexes
- Redis Stream consumer group setup script
- Shared utilities for model validation
- Unit tests for all models (serialization, validation, edge cases)

**Plans:**
- [ ] Plan 2.1: Define NormalizedEvent, DetectionEvent, Incident schemas
- [ ] Plan 2.2: Define IncidentSummary (Claude Structured Output schema) and Alert schema
- [ ] Plan 2.3: Set up MongoDB collections and indexes
- [ ] Plan 2.4: Create Redis Stream consumer groups and stream key naming utilities
- [ ] Plan 2.5: Write unit tests for all models

**Acceptance Criteria:**
- All models pass Pydantic validation
- MongoDB indexes created and verified
- Redis consumer groups created
- Unit tests pass (100% model coverage)

---

### Phase 3: Ingestion Agent — CloudTrail Log Ingestion & Normalization
**Status:** ⬜ Not Started  
**Objective:** Build Ingestion Agent to read AWS CloudTrail logs, normalize to NormalizedEvent, store in S3 + MongoDB, publish to Redis stream  
**Requirements:** REQ-03  
**Depends on:** Phase 2  
**Duration:** 2 days

**Deliverables:**
- CloudTrail event parser (JSON format)
- NormalizedEvent transformer (extract user, ip, action, timestamp)
- S3 storage layer with tenant_id prefix
- MongoDB event storage with tenant isolation
- Redis Stream publisher
- ARQ worker integration
- Error handling and retry logic
- Unit + integration tests (synthetic CloudTrail logs)

**Plans:**
- [ ] Plan 3.1: Parse AWS CloudTrail JSON and map to NormalizedEvent fields
- [ ] Plan 3.2: Implement S3 storage with tenant_id prefix and raw log archiving
- [ ] Plan 3.3: Implement MongoDB event storage with tenant_id queries
- [ ] Plan 3.4: Implement Redis Stream publisher (`soc:events:{tenant_id}`)
- [ ] Plan 3.5: Integrate ARQ worker and test ingestion pipeline

**Acceptance Criteria:**
- CloudTrail JSON → NormalizedEvent transformation accurate
- S3 logs stored with correct tenant prefix
- MongoDB events queryable by tenant_id and timestamp
- Redis Stream consumer receives events
- End-to-end integration test passes

---

### Phase 4: Detection Agent — Sigma Rules & Anomaly Detection
**Status:** ⬜ Not Started  
**Objective:** Build Detection Agent to apply 5 Sigma rules, score detections, map to MITRE ATT&CK, publish to Redis stream  
**Requirements:** REQ-04  
**Depends on:** Phase 3  
**Duration:** 2-3 days

**Deliverables:**
- 5 Sigma detection rules (YAML format):
  1. Brute force logins (>5 failed ConsoleLogin in 10 min)
  2. Login from new geo (IP geolocation change)
  3. Privilege escalation (AssumeRole or root access)
  4. Unusual access hours (login outside 9-17 business hours)
  5. Root account usage (direct root login)
- sigma-rule-matcher integration
- MITRE ATT&CK mapping (T-code lookup from enterprise-attack.json)
- Detection scoring (0-100 inverse correlation with false positives)
- ARQ worker integration
- Unit + integration tests (synthetic NormalizedEvent logs)

**Plans:**
- [ ] Plan 4.1: Write 5 Sigma rules in YAML format with selection criteria
- [ ] Plan 4.2: Integrate sigma-rule-matcher for rule evaluation
- [ ] Plan 4.3: Load MITRE ATT&CK data and map technique IDs
- [ ] Plan 4.4: Implement detection scoring algorithm
- [ ] Plan 4.5: Implement Redis Stream publisher (`soc:detections:{tenant_id}`)
- [ ] Plan 4.6: Integrate ARQ worker and test detection pipeline

**Acceptance Criteria:**
- All 5 Sigma rules parse correctly
- Rule matches produce DetectionEvent with severity and MITRE T-code
- Detection scoring is reproducible and reasonable
- End-to-end test (NormalizedEvent → DetectionEvent) passes
- False positive rate <20% on synthetic data

---

### Phase 5: Correlation Agent — Graph-Based Incident Clustering
**Status:** ⬜ Not Started  
**Objective:** Build Correlation Agent to cluster detections by user+IP within 60-min window using NetworkX, create incidents  
**Requirements:** REQ-05  
**Depends on:** Phase 4  
**Duration:** 2 days

**Deliverables:**
- NetworkX graph construction (user nodes, IP nodes, detection edges)
- 60-minute sliding window logic
- Detection grouping and incident creation
- Incident metadata (entities, detection_ids, severity)
- Redis Stream publisher
- ARQ worker integration
- Unit + integration tests (multi-detection scenarios)

**Plans:**
- [ ] Plan 5.1: Build NetworkX graph with user and IP nodes
- [ ] Plan 5.2: Implement 60-minute sliding window for clustering
- [ ] Plan 5.3: Implement incident creation and entity list generation
- [ ] Plan 5.4: Implement Redis Stream publisher (`soc:incidents:{tenant_id}`)
- [ ] Plan 5.5: Integrate ARQ worker and test correlation pipeline

**Acceptance Criteria:**
- Graph construction accurate (nodes, edges)
- 60-minute window correctly filters detections
- Incidents group related detections
- End-to-end test (DetectionEvent → Incident) passes
- Correlation reduces false positives by 30-40%

---

### Phase 6: Investigation Agent — Claude-Powered Incident Analysis
**Status:** ⬜ Not Started  
**Objective:** Build Investigation Agent to call Claude API with Structured Output, generate IncidentSummary narratives  
**Requirements:** REQ-06  
**Depends on:** Phase 5  
**Duration:** 2 days

**Deliverables:**
- Claude API client with Structured Output schema
- IncidentSummary schema (summary, what_happened, why_suspicious, impact, recommended_action, severity)
- System prompt (no hallucination, data-only analysis)
- Error handling and retry logic
- ARQ worker integration
- Unit tests (mocked Claude responses)
- Integration tests (real Claude API calls on non-prod tier)

**Plans:**
- [ ] Plan 6.1: Set up Claude API client with Anthropic SDK
- [ ] Plan 6.2: Define IncidentSummary schema and validate with Claude API
- [ ] Plan 6.3: Write system prompt forbidding hallucination and inference
- [ ] Plan 6.4: Implement investigation logic and error handling
- [ ] Plan 6.5: Implement Redis Stream publisher (`soc:summaries:{tenant_id}`)
- [ ] Plan 6.6: Integrate ARQ worker and test investigation pipeline

**Acceptance Criteria:**
- Claude API calls return valid IncidentSummary
- System prompt followed (no inferred information)
- Error handling for API failures graceful
- End-to-end test (Incident → IncidentSummary) passes
- Cost tracking for API usage in place

---

### Phase 7: Alerting Agent — Email Delivery & Feedback Loop
**Status:** ⬜ Not Started  
**Objective:** Build Alerting Agent to send email alerts and capture TP/FP feedback  
**Requirements:** REQ-07, REQ-08 (feedback endpoint)  
**Depends on:** Phase 6  
**Duration:** 1-2 days

**Deliverables:**
- Email template (HTML + plain text)
- fastapi-mail integration
- Alert record creation in MongoDB
- Feedback endpoint (`/api/feedback/{alert_id}`)
- Feedback data model and MongoDB storage
- ARQ worker integration
- Unit + integration tests (mocked email service)

**Plans:**
- [ ] Plan 7.1: Design email template with incident summary and action links
- [ ] Plan 7.2: Integrate fastapi-mail (SMTP or AWS SES)
- [ ] Plan 7.3: Implement feedback endpoint and data model
- [ ] Plan 7.4: Implement Alert record creation and MongoDB storage
- [ ] Plan 7.5: Integrate ARQ worker and test alerting pipeline

**Acceptance Criteria:**
- Email sends successfully
- Feedback endpoint receives and stores TP/FP correctly
- End-to-end test (IncidentSummary → Alert) passes
- Alert includes all required metadata

---

### Phase 8: FastAPI Broker & REST API
**Status:** ⬜ Not Started  
**Objective:** Build FastAPI Broker to expose REST endpoints, manage tenants, handle authentication, rate limiting  
**Requirements:** REQ-08  
**Depends on:** Phase 2  
**Duration:** 2 days

**Deliverables:**
- FastAPI app structure with middleware (auth, logging, rate limiting)
- 5 REST endpoints:
  - `POST /api/tenants/create` — on-board new tenant
  - `POST /api/logs/ingest` — accept CloudTrail/syslog batches
  - `POST /api/feedback/{alert_id}` — receive TP/FP feedback
  - `GET /api/incidents?tenant_id=...` — list incidents
  - `GET /api/health` — readiness probe
- API key authentication per tenant
- Request validation (Pydantic)
- Rate limiting per tenant
- OpenAPI/Swagger documentation
- Unit + integration tests

**Plans:**
- [ ] Plan 8.1: Set up FastAPI app structure with middleware
- [ ] Plan 8.2: Implement tenant management and API key generation
- [ ] Plan 8.3: Implement `/api/logs/ingest` endpoint (enqueue to Ingestion Agent)
- [ ] Plan 8.4: Implement `/api/incidents`, `/api/feedback`, `/api/health` endpoints
- [ ] Plan 8.5: Implement authentication and rate limiting middleware

**Acceptance Criteria:**
- All endpoints functional and documented
- Authentication required and enforced
- Rate limiting prevents abuse
- OpenAPI docs available at `/docs`
- Integration tests pass

---

### Phase 9: Testing, Validation & Quality Assurance
**Status:** ⬜ Not Started  
**Objective:** Comprehensive testing, end-to-end validation, synthetic data generation, coverage reporting  
**Requirements:** REQ-09  
**Depends on:** Phases 3-8 (all agents + broker)  
**Duration:** 2-3 days

**Deliverables:**
- Unit tests (>80% coverage on critical paths)
- Integration tests for each agent
- End-to-end test (CloudTrail → Email alert)
- Synthetic log generation (SALO format)
- Test fixtures and mocking utilities
- Coverage report
- CI/CD pipeline validation
- Performance benchmarks (throughput, latency)

**Plans:**
- [ ] Plan 9.1: Write unit tests for all agents (mocked dependencies)
- [ ] Plan 9.2: Write integration tests with real Redis/MongoDB (Docker)
- [ ] Plan 9.3: Write end-to-end test (log ingest → alert email)
- [ ] Plan 9.4: Generate synthetic test logs (SALO format)
- [ ] Plan 9.5: Measure test coverage and ensure >80% on critical paths
- [ ] Plan 9.6: Validate GitHub Actions CI/CD pipeline

**Acceptance Criteria:**
- All tests pass (unit, integration, end-to-end)
- Coverage >80% on critical agent logic
- End-to-end test produces alert email
- CI/CD pipeline green on all branches
- Performance acceptable (no obvious bottlenecks)

---

### Phase 10: Documentation, Deployment & Launch
**Status:** ⬜ Not Started  
**Objective:** Complete documentation, prepare Docker images, deployment guide, operational runbook  
**Requirements:** REQ-10  
**Depends on:** Phase 9  
**Duration:** 1-2 days

**Deliverables:**
- README.md (setup, development, deployment)
- API documentation (OpenAPI schema)
- Runbook for operational monitoring (logs, metrics, alerts)
- Docker images for all agents and broker
- docker-compose.yml for full stack (prod-ready)
- Environment variable documentation
- Deployment checklist
- Architecture diagram
- Troubleshooting guide

**Plans:**
- [ ] Plan 10.1: Write comprehensive README with setup + deployment steps
- [ ] Plan 10.2: Generate API documentation (export OpenAPI schema)
- [ ] Plan 10.3: Write operational runbook (monitoring, logging, alerts)
- [ ] Plan 10.4: Create Dockerfiles for all agents and broker
- [ ] Plan 10.5: Write deployment guide for AWS/GCP/Azure/on-prem
- [ ] Plan 10.6: Create architecture diagram and troubleshooting guide

**Acceptance Criteria:**
- README covers all setup scenarios
- API docs complete and accurate
- Docker images build and run
- docker-compose.yml deploys full stack locally
- Deployment guide is actionable
- All documentation passes spell/grammar check

---

## Progress Summary

| Phase | Name | Status | Plans | Complete | Depends On |
|-------|------|--------|-------|----------|-----------|
| 1 | Foundation & Infrastructure | ⬜ | 5 | 0/5 | — |
| 2 | Data Models & DB Schema | ⬜ | 5 | 0/5 | Phase 1 |
| 3 | Ingestion Agent | ⬜ | 5 | 0/5 | Phase 2 |
| 4 | Detection Agent | ⬜ | 6 | 0/6 | Phase 3 |
| 5 | Correlation Agent | ⬜ | 5 | 0/5 | Phase 4 |
| 6 | Investigation Agent | ⬜ | 6 | 0/6 | Phase 5 |
| 7 | Alerting Agent | ⬜ | 5 | 0/5 | Phase 6 |
| 8 | FastAPI Broker | ⬜ | 5 | 0/5 | Phase 2 |
| 9 | Testing & QA | ⬜ | 6 | 0/6 | Phases 3-8 |
| 10 | Documentation & Deploy | ⬜ | 6 | 0/6 | Phase 9 |

**Total Plans:** 54  
**Total Complete:** 0

---

## Timeline (Estimated)

| Phase | Started | Completed | Duration | Status |
|-------|---------|-----------|----------|--------|
| 1 | — | — | 1-2 days | ⬜ Not Started |
| 2 | — | — | 1 day | ⬜ Not Started |
| 3 | — | — | 2 days | ⬜ Not Started |
| 4 | — | — | 2-3 days | ⬜ Not Started |
| 5 | — | — | 2 days | ⬜ Not Started |
| 6 | — | — | 2 days | ⬜ Not Started |
| 7 | — | — | 1-2 days | ⬜ Not Started |
| 8 | — | — | 2 days | ⬜ Not Started |
| 9 | — | — | 2-3 days | ⬜ Not Started |
| 10 | — | — | 1-2 days | ⬜ Not Started |

**Total Duration:** 15-20 days (aggressive execution)

---

## Wave Execution Strategy

### Wave 1 (Parallel Foundation)
Phases 1, 2, 8 can run in parallel (no interdependencies before phase 3 starts).
- Phase 1: Infrastructure setup
- Phase 2: Data models
- Phase 8: API broker skeleton (doesn't need agents yet)

### Wave 2 (Agent Pipeline)
Phases 3-7 run sequentially (each depends on previous output).
- Phase 3: Ingestion (produces NormalizedEvent)
- Phase 4: Detection (consumes NormalizedEvent)
- Phase 5: Correlation (consumes DetectionEvent)
- Phase 6: Investigation (consumes Incident)
- Phase 7: Alerting (consumes IncidentSummary)

### Wave 3 (Validation & Launch)
Phases 9, 10 run after all agents complete.
- Phase 9: Comprehensive testing
- Phase 10: Documentation and deployment

---

## Risk Factors

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Claude API quota exceeded | Medium | High | Monitor costs, implement rate limiting, feedback loop optimization |
| Redis/MongoDB downtime | Low | High | Use Docker Compose for easy reset, implement dead-letter queues |
| Sigma rule false positives | High | Medium | Start with conservative thresholds, use feedback loop to tune |
| Team unfamiliar with ARQ | Medium | Low | Pair programming on Phase 3, review ARQ docs before Phase 3 |
| S3/CloudTrail AWS costs | Low | Low | Use LocalStack for dev, cost estimation tool for prod |

---

## Dependencies Map

```
Phase 1 (Foundation)
  ↓
Phase 2 (Models) ←─── Phase 8 (Broker API)
  ↓
Phase 3 (Ingestion)
  ↓
Phase 4 (Detection)
  ↓
Phase 5 (Correlation)
  ↓
Phase 6 (Investigation)
  ↓
Phase 7 (Alerting)
  ↓
Phase 9 (Testing)
  ↓
Phase 10 (Documentation & Deploy)
```

---

## Next Steps

1. ✅ Finalize SPEC.md (DONE)
2. ✅ Create ROADMAP.md (DONE)
3. 📋 Execute Phase 1 (Foundation & Infrastructure)
4. 📋 Execute Phase 2 (Data Models)
5. 📋 Execute Phases 3-7 (Agent Pipeline)
6. 📋 Execute Phase 9 (Testing)
7. 📋 Execute Phase 10 (Documentation & Deploy)

---

**Status: READY FOR EXECUTION** ✅  
Specification locked, phases defined, dependencies mapped.  
Ready to begin Wave 1 (Phase 1).
