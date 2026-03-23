"""Alerting Agent — Email delivery with fastapi-mail and TP/FP feedback collection."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Literal

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jinja2 import Environment, FileSystemLoader

from db.mongo import connect_mongo, get_collection
from db.redis_client import connect_redis, get_redis, xack
from shared.config import settings
from shared.models import Alert, Incident

logger = logging.getLogger(__name__)

_jinja_env = Environment(loader=FileSystemLoader("email_templates"), autoescape=True)


async def run_alerting_agent(ctx, *, tenant_id: str, **fields) -> dict:
    data: dict = {"tenant_id": tenant_id}
    for k, v in fields.items():
        try:
            data[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            data[k] = None if v == "None" else v

    try:
        incident = Incident(**data)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    alerts_col = get_collection("alerts")

    # Idempotency — one alert per incident, ever
    existing = await alerts_col.find_one({"tenant_id": tenant_id, "incident_id": incident.incident_id})
    if existing:
        return {"status": "duplicate"}

    if not incident.summary:
        return {"status": "skip", "reason": "no summary yet"}

    summary = incident.summary
    users_col = get_collection("users")
    user = await users_col.find_one({"tenant_id": tenant_id, "user_id": tenant_id})
    email = user.get("email", "") if user else ""

    # Determine entity and IP from first detection
    detections_col = get_collection("detections")
    first_det = await detections_col.find_one({"tenant_id": tenant_id, "detection_id": {"$in": incident.detection_ids}})
    raw = first_det.get("raw_event", {}) if first_det else {}
    affected_entity = raw.get("user", "unknown")
    source_ip = raw.get("ip", "unknown")
    location = f"{raw.get('city', '')}, {raw.get('country', '')}".strip(", ")
    source_type = raw.get("source", "cloudtrail")

    alert = Alert(
        tenant_id=tenant_id,
        incident_id=incident.incident_id,
        recipient=email or "unset@mcp-soc.io",
        title=summary.summary[:120],
        severity=incident.severity,
        affected_entity=affected_entity,
        source_ip=source_ip,
        location=location or "unknown",
        source_type=source_type,
        incident_summary=summary.what_happened,
        recommended_action=summary.recommended_action,
    )

    # Insert BEFORE sending (idempotency on retry)
    await alerts_col.insert_one(alert.model_dump())

    # Send email
    if email and settings.SENDGRID_API_KEY:
        try:
            html = _jinja_env.get_template("incident_alert.html").render(
                alert=alert,
                summary=summary,
                incident=incident,
                feedback_tp_url=f"{settings.API_BASE_URL}/incidents/{incident.incident_id}/feedback",
                frontend_url=settings.FRONTEND_URL,
            )
            sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            message = Mail(
                from_email=settings.ALERT_FROM_EMAIL,
                to_emails=email,
                subject=f"[{alert.severity.upper()}] SOC Alert: {alert.title}",
                html_content=html,
            )
            sg.send(message)
        except Exception as e:
            # Log but don't fail — alert is already stored
            print(f"Email send failed: {e}")

    # Audit log
    audit_col = get_collection("audit_log")
    await audit_col.insert_one({
        "tenant_id": tenant_id,
        "action": "alert_sent",
        "entity": "alert",
        "entity_id": alert.alert_id,
        "incident_id": incident.incident_id,
        "timestamp": datetime.utcnow(),
    })

    return {"status": "ok", "alert_id": alert.alert_id}


async def startup(ctx):
    await connect_mongo()
    await connect_redis()
    asyncio.create_task(_poll_summaries(ctx))


async def _poll_summaries(ctx):
    r = get_redis()
    while ctx.get("running", True):
        try:
            keys = await r.keys("soc:summaries:*")
            for key in keys:
                tenant_id = key.split(":")[-1]
                try:
                    await r.xgroup_create(key, "alerting", id="0", mkstream=True)
                except Exception:
                    pass
                try:
                    msgs = await r.xreadgroup("alerting", "alerting-1", {key: ">"}, count=10, block=500)
                except Exception:
                    continue
                if msgs:
                    for _stream, entries in msgs:
                        for msg_id, fields in entries:
                            await run_alerting_agent(ctx, **fields)
                            await r.xack(key, "alerting", msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.1)


async def shutdown(ctx):
    ctx["running"] = False


class WorkerSettings:
    functions = [run_alerting_agent]
    on_startup = startup
    on_shutdown = shutdown
    from arq.connections import RedisSettings as _RS
    redis_settings = _RS.from_dsn(settings.REDIS_URL)
