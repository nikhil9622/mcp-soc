"""UEBA — User and Entity Behavior Analytics.

Computes behavioral baselines from the last 30 days of events.
Flags anomalies: unusual hours, new actions, new IPs, volume spikes.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt
from fastapi import APIRouter, Depends
from db.mongo import get_collection
from api.dependencies import get_current_user

router = APIRouter(prefix="/ueba", tags=["ueba"])

BASELINE_DAYS  = 30
RECENT_DAYS    = 1       # "recent" window for anomaly detection
MIN_EVENTS     = 5       # need at least this many baseline events


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return sqrt(sum((v - m) ** 2 for v in values) / len(values))


def _anomaly_score(baseline: dict, recent: dict) -> tuple[float, list[str]]:
    """Return 0-100 risk score + list of anomaly reasons."""
    reasons: list[str] = []
    score = 0.0

    # 1. Unusual hour
    baseline_hours = set(baseline.get("common_hours", []))
    recent_hours   = set(recent.get("hours", []))
    odd_hours = recent_hours - baseline_hours
    if odd_hours and baseline_hours:
        score += 25
        hours_str = ", ".join(str(h) + ":00" for h in sorted(odd_hours))
        reasons.append(f"Activity at unusual hours: {hours_str}")

    # 2. New actions not seen in baseline
    baseline_actions = set(baseline.get("common_actions", []))
    recent_actions   = set(recent.get("actions", []))
    new_actions = recent_actions - baseline_actions
    if new_actions and baseline_actions:
        score += 20
        reasons.append(f"New action types: {', '.join(list(new_actions)[:3])}")

    # 3. New IPs not seen in baseline
    baseline_ips = set(baseline.get("common_ips", []))
    recent_ips   = set(recent.get("ips", []))
    new_ips = {ip for ip in recent_ips - baseline_ips if ip not in ("0.0.0.0", "unknown")}
    if new_ips and baseline_ips:
        score += 20
        reasons.append(f"New source IPs: {', '.join(list(new_ips)[:3])}")

    # 4. Volume spike (> 2 std devs above daily mean)
    daily_mean = baseline.get("daily_mean", 0)
    daily_std  = baseline.get("daily_std", 0)
    recent_vol = recent.get("event_count", 0)
    if daily_mean > 0 and daily_std > 0:
        z = (recent_vol - daily_mean) / daily_std
        if z > 2:
            score += min(35, int(z * 10))
            reasons.append(f"Volume spike: {recent_vol} events (mean={daily_mean:.0f}, z={z:.1f})")
    elif daily_mean > 0 and recent_vol > daily_mean * 3:
        score += 20
        reasons.append(f"Volume spike: {recent_vol} vs baseline mean {daily_mean:.0f}")

    return min(100.0, score), reasons


async def _build_entity_profile(tenant_id: str, entity_field: str, entity_value: str,
                                events_col) -> dict:
    """Compute baseline + recent anomaly for one user or IP."""
    now      = datetime.utcnow()
    baseline_since = now - timedelta(days=BASELINE_DAYS)
    recent_since   = now - timedelta(days=RECENT_DAYS)

    match = {"tenant_id": tenant_id, entity_field: entity_value}

    # Baseline events (30d)
    baseline_events = await events_col.find(
        {**match, "timestamp": {"$gte": baseline_since, "$lt": recent_since}},
        {"timestamp": 1, "action": 1, "ip": 1, "user": 1},
    ).to_list(5000)

    # Recent events (1d)
    recent_events = await events_col.find(
        {**match, "timestamp": {"$gte": recent_since}},
        {"timestamp": 1, "action": 1, "ip": 1, "user": 1},
    ).to_list(1000)

    if len(baseline_events) < MIN_EVENTS and not recent_events:
        return {}

    # Build baseline
    hour_counts: defaultdict[int, int] = defaultdict(int)
    action_counts: defaultdict[str, int] = defaultdict(int)
    ip_counts: defaultdict[str, int] = defaultdict(int)
    daily_counts: defaultdict[str, int] = defaultdict(int)

    for e in baseline_events:
        ts = e.get("timestamp")
        if isinstance(ts, str):
            try: ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except: continue
        if ts:
            hour_counts[ts.hour] += 1
            daily_counts[ts.strftime("%Y-%m-%d")] += 1
        action_counts[e.get("action", "unknown")] += 1
        ip_counts[e.get("ip", "0.0.0.0")] += 1

    daily_vals = list(daily_counts.values())
    daily_mean = sum(daily_vals) / len(daily_vals) if daily_vals else 0
    daily_std  = _std([float(v) for v in daily_vals])

    # Top hours (those covering 80% of activity)
    total_h = sum(hour_counts.values()) or 1
    sorted_hours = sorted(hour_counts.items(), key=lambda x: -x[1])
    cumulative, common_hours = 0, []
    for h, cnt in sorted_hours:
        common_hours.append(h)
        cumulative += cnt
        if cumulative / total_h >= 0.8:
            break

    common_actions = [a for a, _ in sorted(action_counts.items(), key=lambda x: -x[1])[:10]]
    common_ips     = [ip for ip, _ in sorted(ip_counts.items(), key=lambda x: -x[1])[:10]]

    baseline = {
        "event_count":   len(baseline_events),
        "common_hours":  common_hours,
        "common_actions": common_actions,
        "common_ips":    common_ips,
        "daily_mean":    daily_mean,
        "daily_std":     daily_std,
        "hour_distribution": dict(hour_counts),
        "action_distribution": dict(action_counts),
    }

    # Recent summary
    recent_hours_set   = set()
    recent_actions_set = set()
    recent_ips_set     = set()
    for e in recent_events:
        ts = e.get("timestamp")
        if isinstance(ts, str):
            try: ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except: pass
        if ts and isinstance(ts, datetime):
            recent_hours_set.add(ts.hour)
        recent_actions_set.add(e.get("action", "unknown"))
        ip = e.get("ip", "")
        if ip:
            recent_ips_set.add(ip)

    recent = {
        "event_count": len(recent_events),
        "hours":       list(recent_hours_set),
        "actions":     list(recent_actions_set),
        "ips":         list(recent_ips_set),
    }

    risk_score, reasons = _anomaly_score(baseline, recent)

    return {
        "entity":       entity_value,
        "entity_type":  "user" if entity_field == "user" else "ip",
        "baseline":     baseline,
        "recent":       recent,
        "risk_score":   risk_score,
        "anomalies":    reasons,
        "is_anomalous": risk_score >= 25,
    }


@router.get("/entities")
async def list_entities(tenant_id: str = Depends(get_current_user)):
    """Return all users and IPs with their risk scores."""
    events_col = get_collection("events")
    since = datetime.utcnow() - timedelta(days=BASELINE_DAYS)

    # Distinct users
    users = await events_col.distinct("user", {"tenant_id": tenant_id, "timestamp": {"$gte": since}})
    # Distinct IPs
    ips   = await events_col.distinct("ip",   {"tenant_id": tenant_id, "timestamp": {"$gte": since}})

    results = []
    for u in [u for u in users if u and u not in ("unknown", "")][:30]:
        profile = await _build_entity_profile(tenant_id, "user", u, events_col)
        if profile:
            results.append(profile)

    for ip in [ip for ip in ips if ip and ip not in ("0.0.0.0", "")][:20]:
        profile = await _build_entity_profile(tenant_id, "ip", ip, events_col)
        if profile:
            results.append(profile)

    results.sort(key=lambda x: -x.get("risk_score", 0))
    return {"entities": results, "total": len(results)}


@router.get("/entity/{entity_value}")
async def get_entity(entity_value: str, tenant_id: str = Depends(get_current_user)):
    """Detailed behavioral profile for one user or IP."""
    events_col = get_collection("events")

    # Try as user first, then IP
    profile = await _build_entity_profile(tenant_id, "user", entity_value, events_col)
    if not profile:
        profile = await _build_entity_profile(tenant_id, "ip", entity_value, events_col)
    if not profile:
        return {"entity": entity_value, "risk_score": 0, "anomalies": [], "baseline": {}, "recent": {}}
    return profile
