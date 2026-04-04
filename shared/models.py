from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class NormalizedEvent(BaseModel):
    tenant_id: str
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime
    source: Literal["cloudtrail", "syslog", "app"]
    user: str
    user_type: str = "IAMUser"
    ip: str
    action: str
    region: str | None = None
    city: str | None = None
    country: str | None = None
    is_new_location: bool = False
    raw_log_s3_key: str | None = None
    metadata: dict = {}


class DetectionEvent(BaseModel):
    detection_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    event_id: str
    rule_id: str
    rule_name: str
    mitre_technique_id: str
    mitre_tactic: str
    severity: Literal["critical", "high", "medium", "low"]
    risk_score: float
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    raw_event: dict = {}


class IncidentSummary(BaseModel):
    summary: str
    what_happened: str
    why_suspicious: str
    impact: str
    recommended_action: str
    severity: Literal["critical", "high", "medium", "low"]


class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    detection_ids: list[str]
    entities: dict[str, list[str]] = Field(default_factory=dict)  # {"users": [...], "ips": [...]}
    status: Literal["open", "investigating", "closed"] = "open"
    severity: Literal["critical", "high", "medium", "low"]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: IncidentSummary | None = None


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    incident_id: str
    recipient: str                          # Email address
    severity: Literal["critical", "high", "medium", "low"]
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    feedback: Literal["tp", "fp", None] = None  # True positive / False positive
    feedback_at: datetime | None = None
    feedback_note: str | None = None
    # Legacy fields (for backward compatibility)
    title: str = ""
    affected_entity: str = ""
    source_ip: str = ""
    location: str = ""
    source_type: Literal["cloudtrail", "syslog", "app"] = "cloudtrail"
    incident_summary: str = ""
    recommended_action: str = ""


class User(BaseModel):
    user_id: str
    email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    plan: str = "free"
    settings: dict = {}
    api_key_hash: str | None = None
    api_key_prefix: str | None = None


class SyslogPayload(BaseModel):
    records: list[dict]


class CloudTrailPayload(BaseModel):
    records: list[dict]


class FeedbackRequest(BaseModel):
    feedback: Literal["tp", "fp"]


class IsolationRequest(BaseModel):
    type: Literal["ip", "user"]
    value: str


class CaseNote(BaseModel):
    note_id: str = Field(default_factory=lambda: str(uuid4()))
    author: str
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CaseTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    done: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Case(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    title: str
    description: str = ""
    status: Literal["open", "in_progress", "resolved", "closed"] = "open"
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    assignee: str = ""
    incident_ids: list[str] = Field(default_factory=list)
    notes: list[CaseNote] = Field(default_factory=list)
    tasks: list[CaseTask] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CreateCaseRequest(BaseModel):
    title: str
    description: str = ""
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    assignee: str = ""
    incident_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class AddNoteRequest(BaseModel):
    body: str
    author: str = "analyst"


class AddTaskRequest(BaseModel):
    title: str


class UpdateCaseRequest(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"] | None = None
    priority: Literal["critical", "high", "medium", "low"] | None = None
    assignee: str | None = None
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class Device(BaseModel):
    tenant_id: str
    device_id: str
    device_name: str
    os: str
    ip: str
    mac: str = ""
    agent_version: str = "1.0.0"
    registered_by: str
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    events_sent: int = 0


class TeamMember(BaseModel):
    tenant_id: str
    user_id: str | None = None
    email: str
    role: Literal["soc_manager", "analyst_l1", "analyst_l2", "readonly"] = "analyst_l1"
    status: Literal["pending", "active", "removed"] = "pending"
    invited_by: str
    invited_at: datetime = Field(default_factory=datetime.utcnow)
    accepted_at: datetime | None = None
    invite_token: str = Field(default_factory=lambda: str(uuid4()))
