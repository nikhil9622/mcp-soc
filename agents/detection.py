"""Detection Agent — matches Sigma rules against normalized events."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import yaml

from db.mongo import connect_mongo, get_collection
from db.redis_client import connect_redis, xadd, xack, get_redis
from shared.config import settings
from shared.models import DetectionEvent, NormalizedEvent

SEVERITY_BASE = {"critical": 10.0, "high": 7.0, "medium": 5.0, "low": 2.0}


def load_sigma_rules(rules_dir: str = "detection_rules") -> list[dict]:
    rules = []
    p = Path(rules_dir)
    if not p.exists():
        return rules
    for f in p.glob("*.yaml"):
        try:
            with open(f) as fh:
                rule = yaml.safe_load(fh)
                rule["_file"] = str(f)
                rules.append(rule)
        except Exception:
            pass
    return rules


def _get_mitre_id(tags: list[str]) -> tuple[str, str]:
    for tag in tags:
        if tag.startswith("attack.t") or tag.startswith("attack.T"):
            parts = tag.split(".")
            if len(parts) >= 2:
                tid = parts[1].upper()
                if not tid.startswith("T"):
                    tid = "T" + tid
                return tid, parts[0].replace("attack.", "")
    return "T0000", "unknown"


def _match_rule(rule: dict, event: NormalizedEvent) -> bool:
    """Simple structural matcher for MVP Sigma rules."""
    detection = rule.get("detection", {})
    logsource = rule.get("logsource", {})

    # Source filter
    source_product = logsource.get("product", "")
    if source_product == "aws" and event.source != "cloudtrail":
        return False
    if source_product == "linux" and event.source != "syslog":
        return False
    if source_product == "windows" and event.source != "syslog":
        return False

    selection = detection.get("selection", {})
    match_type = rule.get("match_type", "")

    # match_type: time_range — check if event timestamp is outside business hours
    if match_type == "time_range":
        hour = event.timestamp.hour
        start = rule.get("business_hours_start", 6)
        end = rule.get("business_hours_end", 22)
        return not (start <= hour < end)

    # match_type: new_location
    if match_type == "new_location":
        return event.is_new_location

    # match_type: threshold — handled at stream level, not per-event
    if match_type == "threshold":
        return False  # Threshold rules need stateful counting — skip for MVP per-event matching

    # Structural matching: check all selection fields against event fields
    for field, expected in selection.items():
        # Map Sigma field names to NormalizedEvent fields
        actual = _get_event_field(event, field)
        if actual is None:
            return False
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif str(actual) != str(expected):
            return False
    return bool(selection)


def _get_event_field(event: NormalizedEvent, field: str):
    # Direct fields
    mapping = {
        "eventName": event.action,
        "action": event.action,
        "user": event.user,
        "user_type": event.user_type,
        "source": event.source,
        "ip": event.ip,
    }
    if field in mapping:
        return mapping[field]
    # Nested metadata
    return event.metadata.get(field)


async def run_detection_agent(ctx, *, tenant_id: str, **event_fields) -> dict:
    # Reconstruct NormalizedEvent from fields
    # Fields may be stringified
    data: dict = {"tenant_id": tenant_id}
    for k, v in event_fields.items():
        try:
            data[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            data[k] = None if v == "None" else v

    try:
        event = NormalizedEvent(**data)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    rules: list[dict] = ctx.get("sigma_rules", [])
    mitre_data: dict = ctx.get("mitre_data", {})
    detections_col = get_collection("detections")

    fired = []
    for rule in rules:
        if not _match_rule(rule, event):
            continue

        tags = rule.get("tags", [])
        technique_id, tactic = _get_mitre_id(tags)
        mitre_info = mitre_data.get(technique_id, {})
        severity = rule.get("level", "medium")
        base = SEVERITY_BASE.get(severity, 5.0)
        is_root = event.user_type == "Root"
        priv_mult = settings.RISK_PRIVILEGE_HIGH if is_root else settings.RISK_PRIVILEGE_LOW
        asset_mult = settings.RISK_ASSET_CRITICAL if is_root else settings.RISK_ASSET_LOW
        risk_score = base * priv_mult * asset_mult

        det = DetectionEvent(
            tenant_id=tenant_id,
            event_id=event.event_id,
            rule_id=rule.get("id", "unknown"),
            rule_name=rule.get("title", "unknown"),
            mitre_technique_id=technique_id,
            mitre_tactic=mitre_info.get("tactic", tactic),
            severity=severity,
            risk_score=risk_score,
            raw_event=event.model_dump(mode="json"),
        )

        # Store
        try:
            await detections_col.insert_one(det.model_dump())
        except Exception:
            pass  # duplicate

        # Enqueue for correlation
        await xadd("detections", tenant_id, det.model_dump(mode="json"))
        fired.append(det.detection_id)

    return {"status": "ok", "fired": len(fired)}


async def startup(ctx):
    await connect_mongo()
    await connect_redis()
    ctx["sigma_rules"] = load_sigma_rules()
    ctx["mitre_data"] = _load_mitre()
    asyncio.create_task(_poll_events(ctx))


def _load_mitre() -> dict:
    try:
        with open("data/enterprise-attack.json") as f:
            bundle = json.load(f)
        data = {}
        for obj in bundle.get("objects", []):
            if obj.get("type") != "attack-pattern":
                continue
            for ref in obj.get("external_references", []):
                ext_id = ref.get("external_id", "")
                if ref.get("source_name") == "mitre-attack" and ext_id.startswith("T"):
                    phases = obj.get("kill_chain_phases", [])
                    tactic = phases[0]["phase_name"] if phases else "unknown"
                    data[ext_id] = {"name": obj["name"], "tactic": tactic}
        return data
    except Exception:
        return {}


async def _poll_events(ctx):
    r = get_redis()
    while ctx.get("running", True):
        try:
            keys = await r.keys("soc:events:*")
            for key in keys:
                tenant_id = key.split(":")[-1]
                try:
                    await r.xgroup_create(key, "detection", id="0", mkstream=True)
                except Exception:
                    pass
                try:
                    msgs = await r.xreadgroup(
                        "detection", "detection-1", {key: ">"}, count=10, block=500
                    )
                except Exception:
                    continue
                if msgs:
                    for _stream, entries in msgs:
                        for msg_id, fields in entries:
                            await run_detection_agent(ctx, **fields)
                            await xack("events", tenant_id, "detection", msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.1)


async def shutdown(ctx):
    ctx["running"] = False


class WorkerSettings:
    functions = [run_detection_agent]
    on_startup = startup
    on_shutdown = shutdown
    from arq.connections import RedisSettings as _RS
    redis_settings = _RS.from_dsn(settings.REDIS_URL)
