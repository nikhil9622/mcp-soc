"""Investigation Agent — Claude Structured Outputs for incident summaries."""
from __future__ import annotations

import asyncio
import json
import logging

import anthropic

from db.mongo import connect_mongo, get_collection
from db.redis_client import connect_redis, xadd, get_redis
from shared.config import settings
from shared.models import Incident, IncidentSummary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a SOC analyst. "
    "Base your analysis ONLY on the provided event data. "
    "Do not infer, assume, or add information not present in the input. "
    "Provide concise, factual analysis grounded in the detection data."
)


async def run_investigation_agent(ctx, *, tenant_id: str, **fields) -> dict:
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

    incidents_col = get_collection("incidents")
    detections_col = get_collection("detections")

    # Gather detection context
    detections = await detections_col.find(
        {"tenant_id": tenant_id, "detection_id": {"$in": incident.detection_ids}},
        {"_id": 0},
    ).to_list(length=50)

    context = {
        "incident_id": incident.incident_id,
        "tenant_id": tenant_id,
        "severity": incident.severity,
        "created_at": incident.created_at.isoformat(),
        "detections": detections,
    }

    client: anthropic.Anthropic = ctx.get("anthropic_client")

    summary: IncidentSummary | None = None
    if client and settings.ANTHROPIC_API_KEY:
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(context, default=str)}],
                tools=[{
                    "name": "create_incident_summary",
                    "description": "Create a structured incident summary for the SOC analyst.",
                    "input_schema": IncidentSummary.model_json_schema(),
                }],
                tool_choice={"type": "tool", "name": "create_incident_summary"},
            )
            tool_use = next((b for b in response.content if b.type == "tool_use"), None)
            if tool_use:
                summary = IncidentSummary(**tool_use.input)
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")

    if summary is None:
        # Fallback: generate summary from detection data without LLM
        rules = list({d.get("rule_name", "unknown") for d in detections})
        users = list({d.get("raw_event", {}).get("user", "") for d in detections if d.get("raw_event", {}).get("user")})
        ips = list({d.get("raw_event", {}).get("ip", "") for d in detections if d.get("raw_event", {}).get("ip") and d.get("raw_event", {}).get("ip") != "0.0.0.0"})
        summary = IncidentSummary(
            summary=f"Incident with {len(detections)} detections from rules: {', '.join(rules[:3])}",
            what_happened=f"Security rules triggered for user(s) {', '.join(users[:3])} from IP(s) {', '.join(ips[:3])}",
            why_suspicious=f"Multiple security rules fired: {', '.join(rules)}",
            impact="Potential security incident — manual review required.",
            recommended_action="Investigate the affected accounts and source IPs. Block suspicious IPs if confirmed malicious.",
            severity=incident.severity,
        )

    # Update incident with summary
    await incidents_col.update_one(
        {"incident_id": incident.incident_id},
        {"$set": {"summary": summary.model_dump()}},
    )

    # Enqueue for alerting
    updated = incident.model_copy(update={"summary": summary})
    await xadd("summaries", tenant_id, updated.model_dump(mode="json"))

    return {"status": "ok", "incident_id": incident.incident_id}


async def startup(ctx):
    await connect_mongo()
    await connect_redis()
    ctx["anthropic_client"] = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    asyncio.create_task(_poll_incidents(ctx))


async def _poll_incidents(ctx):
    r = get_redis()
    while ctx.get("running", True):
        try:
            keys = await r.keys("soc:incidents:*")
            for key in keys:
                tenant_id = key.split(":")[-1]
                try:
                    await r.xgroup_create(key, "investigation", id="0", mkstream=True)
                except Exception:
                    pass
                try:
                    msgs = await r.xreadgroup("investigation", "investigation-1", {key: ">"}, count=5, block=500)
                except Exception:
                    continue
                if msgs:
                    for _stream, entries in msgs:
                        for msg_id, fields in entries:
                            await run_investigation_agent(ctx, **fields)
                            await r.xack(key, "investigation", msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.1)


async def shutdown(ctx):
    ctx["running"] = False


class WorkerSettings:
    functions = [run_investigation_agent]
    on_startup = startup
    on_shutdown = shutdown
    from arq.connections import RedisSettings as _RS
    redis_settings = _RS.from_dsn(settings.REDIS_URL)
