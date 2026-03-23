# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MCP SOC is a greenfield, cloud-based multi-tenant Security Operations Center. Full specification is in [claude.md](claude.md).

## Tech Stack

| Concern | Technology |
|---|---|
| API / Broker | FastAPI + ARQ (async workers) |
| Event bus | **Redis Streams** (persistent, ACK, consumer groups — NOT pub/sub) |
| Databases | MongoDB via `motor` (async) · S3 via `boto3` |
| Detection rules | **Sigma rule format** (YAML) evaluated with `sigma-rule-matcher` |
| ATT&CK mapping | `mitreattack-python` + bundled local `enterprise-attack.json` |
| Correlation | **NetworkX** (graph, entity-based time-windowed clustering) |
| LLM | Anthropic Claude API — **Investigation Agent only** |
| Schema validation | Pydantic v2 everywhere |
| Email | `fastapi-mail` (MVP), Slack/webhooks (future) |
| Linting | Ruff |
| Testing | pytest + pytest-asyncio + SALO synthetic logs |

## Development Commands

```bash
# Install all dependencies
pip install -r requirements.txt

# Run the broker / API
uvicorn broker.main:app --reload

# Run an individual agent
python -m agents.ingestion
python -m agents.detection
python -m agents.correlation
python -m agents.investigation
python -m agents.alerting

# Run ARQ workers (agent workers)
arq agents.ingestion.WorkerSettings
arq agents.detection.WorkerSettings

# Run all tests
pytest

# Run a single test file
pytest tests/test_detection.py -v

# Run tests with output
pytest -s tests/test_correlation.py

# Lint
ruff check .
ruff format .
```

## Architecture

Events flow through five isolated agents via Redis Streams:

```
CloudTrail / Syslog
      ↓
[Ingestion Agent]     → normalize → NormalizedEvent {tenant_id, timestamp, source, user, ip, action, metadata}
      ↓  stream: soc:events
[Detection Agent]     → Sigma rules → DetectionEvent {rule_id, mitre_technique_id, severity, score}
      ↓  stream: soc:detections
[Correlation Agent]   → NetworkX graph (user/IP nodes, 60-min window) → Incident {detection_ids, entities}
      ↓  stream: soc:incidents
[Investigation Agent] → Claude Structured Output → IncidentSummary {summary, what_happened, why_suspicious, impact, action}
      ↓  stream: soc:summaries
[Alerting Agent]      → email delivery → Alert {severity, channel, feedback: tp|fp|null}
```

**MCP Broker** (FastAPI): exposes REST API, enqueues jobs to Redis Streams, manages tenant lifecycle, and serves the feedback endpoint.

**ARQ** replaces Celery as the worker pool — asyncio-native, uses the same Redis instance.

## Hard Rules

- **LLM only in Investigation Agent.** Ingestion, Detection, Correlation, and Alerting must be deterministic code — zero LLM calls.
- **Investigation Agent fires AFTER Correlation**, never on raw detection events directly. LLM on every detection = budget destruction.
- **Tenant isolation on every operation.** Redis Stream keys: `soc:{stream}:{tenant_id}`. MongoDB: every query starts with `{"tenant_id": tenant_id}`. S3: `s3://{bucket}/{tenant_id}/...`.
- **Detection-as-code.** Rules live in `detection_rules/` as Sigma YAML files. No hardcoded detection logic in Python.
- **No hallucination.** Investigation Agent system prompt must say: "Base your analysis only on the provided event data. Do not infer or assume information not present in the input." Use Claude native Structured Outputs (schema-enforced, not prompt-engineered).
- **5 quality rules before 50 noisy ones.** Alert fatigue is the #1 SOC killer. Every false positive trains analysts to ignore alerts.
- **Build the TP/FP feedback endpoint on day one**, even if unused. It is the most valuable long-term data in the system.

## MVP Scope

Build only these — do not expand without explicit instruction:

1. AWS CloudTrail ingestion + normalization
2. Raw log storage (S3) + event storage (MongoDB)
3. 5 Sigma detection rules: brute force logins, login from new geo, privilege escalation, unusual access hours, root account usage
4. Correlation by user + IP (NetworkX, 60-min window)
5. AI incident summary via Claude Structured Outputs
6. Email alert delivery

## Normalized Event Schema (Pydantic)

```python
class NormalizedEvent(BaseModel):
    tenant_id: str
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime
    source: Literal["cloudtrail", "syslog", "app"]
    user: str
    ip: str
    action: str
    raw_log_s3_key: str | None = None
    metadata: dict = {}
```

## Redis Stream Keys

```
soc:events:{tenant_id}        # NormalizedEvent objects
soc:detections:{tenant_id}    # DetectionEvent objects
soc:incidents:{tenant_id}     # Incident objects
soc:summaries:{tenant_id}     # IncidentSummary objects
```

## MongoDB Collections & Required Indexes

```
events:      compound index (tenant_id, timestamp)
detections:  compound index (tenant_id, detected_at), (tenant_id, severity)
incidents:   compound index (tenant_id, status), (tenant_id, created_at)
alerts:      compound index (tenant_id, incident_id)
audit_log:   append-only, never update
```

## Detection Rule Format (Sigma YAML)

```yaml
title: Multiple Failed Logins
id: <uuid4>
status: stable
logsource:
  product: aws
  service: cloudtrail
detection:
  selection:
    eventName: ConsoleLogin
    responseElements.ConsoleLogin: Failure
  condition: selection | count() > 5
tags:
  - attack.t1110        # Brute Force
  - attack.credential_access
level: medium
```

## Investigation Agent Output Schema

```python
class IncidentSummary(BaseModel):
    summary: str
    what_happened: str
    why_suspicious: str
    impact: str
    recommended_action: str
    severity: Literal["critical", "high", "medium", "low"]
```

Pass this as `output_config` JSON schema to Claude API — **not** prompt engineering.

## MITRE ATT&CK Lookup Pattern

```python
# Load ONCE at startup — never call TAXII at detection time
attack_data = MitreAttackData("data/enterprise-attack.json")

# At incident creation time only
technique = attack_data.get_object_by_attack_id("T1110", "attack-pattern")
```

## What NOT to Build

- Full EDR, kernel monitoring, complex ML pipelines (out of scope)
- Per-tenant MongoDB databases (use shared DB + tenant_id field until data residency required)
- Kafka (Redis Streams handles MVP scale; migrate later if needed)
- UI/dashboard (pipeline must work and be tested before any visualization)
- LLM in detection or correlation agents (deterministic only)
