"""Compliance Reporting — maps SOC capabilities to NIST CSF, SOC 2, PCI DSS, ISO 27001."""
from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from db.mongo import get_collection
from api.dependencies import get_current_user, get_current_user_api_key
from fastapi import Header, Request

async def _resolve_tenant(request: Request) -> str:
    """Accept either Bearer JWT or X-API-Key for compliance endpoints."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return await get_current_user_api_key(x_api_key=api_key)
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:])
        return await get_current_user(credentials=creds)
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Authentication required")

router = APIRouter(prefix="/compliance", tags=["compliance"])

# ── Control definitions ────────────────────────────────────────────────────
# Each control maps to a set of capability tags.
# Capability tags are checked against what the SOC actually has active.

FRAMEWORKS: dict[str, list[dict]] = {
    "nist_csf": [
        {"id": "ID.AM-1", "name": "Asset Inventory",            "category": "Identify",  "caps": ["ingestion"]},
        {"id": "ID.AM-2", "name": "Software Inventory",          "category": "Identify",  "caps": ["ingestion"]},
        {"id": "ID.RA-1", "name": "Asset Vulnerability Mgmt",    "category": "Identify",  "caps": ["detection"]},
        {"id": "ID.RA-3", "name": "Threat Intelligence",         "category": "Identify",  "caps": ["ioc_enrichment"]},
        {"id": "PR.AC-1", "name": "Identity Management",         "category": "Protect",   "caps": ["detection", "ueba"]},
        {"id": "PR.AC-4", "name": "Access Control",              "category": "Protect",   "caps": ["detection"]},
        {"id": "PR.AT-1", "name": "User Awareness",              "category": "Protect",   "caps": []},
        {"id": "PR.DS-5", "name": "Data Leak Protection",        "category": "Protect",   "caps": ["detection"]},
        {"id": "PR.PT-1", "name": "Audit Log Review",            "category": "Protect",   "caps": ["ingestion", "detection"]},
        {"id": "DE.AE-1", "name": "Baseline Network Activity",   "category": "Detect",    "caps": ["ueba"]},
        {"id": "DE.AE-2", "name": "Analyze Detected Events",     "category": "Detect",    "caps": ["detection", "correlation"]},
        {"id": "DE.AE-3", "name": "Aggregate Event Data",        "category": "Detect",    "caps": ["ingestion", "correlation"]},
        {"id": "DE.AE-5", "name": "Incident Alert Thresholds",   "category": "Detect",    "caps": ["alerting"]},
        {"id": "DE.CM-1", "name": "Network Monitoring",          "category": "Detect",    "caps": ["ingestion"]},
        {"id": "DE.CM-3", "name": "Personnel Activity Monitor",  "category": "Detect",    "caps": ["ueba", "detection"]},
        {"id": "DE.CM-7", "name": "Unauthorized Activity Monitor","category": "Detect",   "caps": ["detection"]},
        {"id": "DE.DP-4", "name": "Event Detection Communicated","category": "Detect",    "caps": ["alerting"]},
        {"id": "RS.RP-1", "name": "Response Plan",               "category": "Respond",   "caps": ["case_management"]},
        {"id": "RS.CO-2", "name": "Incident Reporting",          "category": "Respond",   "caps": ["alerting", "case_management"]},
        {"id": "RS.AN-1", "name": "Notifications Investigated",  "category": "Respond",   "caps": ["investigation", "case_management"]},
        {"id": "RS.AN-2", "name": "Incident Impact Understood",  "category": "Respond",   "caps": ["investigation"]},
        {"id": "RS.MI-1", "name": "Contain Incidents",           "category": "Respond",   "caps": ["isolation"]},
        {"id": "RS.IM-1", "name": "Response Plans Updated",      "category": "Respond",   "caps": ["case_management"]},
        {"id": "RC.RP-1", "name": "Recovery Plan",               "category": "Recover",   "caps": []},
        {"id": "RC.IM-1", "name": "Recovery Strategies Updated", "category": "Recover",   "caps": []},
    ],
    "soc2": [
        {"id": "CC1.1",  "name": "Control Environment",           "category": "Common",    "caps": ["detection"]},
        {"id": "CC2.1",  "name": "Communication & Info",          "category": "Common",    "caps": ["alerting"]},
        {"id": "CC3.1",  "name": "Risk Assessment",               "category": "Common",    "caps": ["detection", "investigation"]},
        {"id": "CC4.1",  "name": "Monitoring Activities",         "category": "Common",    "caps": ["ingestion", "detection"]},
        {"id": "CC5.1",  "name": "Control Activities",            "category": "Common",    "caps": ["detection"]},
        {"id": "CC6.1",  "name": "Logical Access Controls",       "category": "Logical",   "caps": ["detection", "ueba"]},
        {"id": "CC6.2",  "name": "New Access Registration",       "category": "Logical",   "caps": ["detection"]},
        {"id": "CC6.3",  "name": "Access Removal",                "category": "Logical",   "caps": ["isolation"]},
        {"id": "CC6.6",  "name": "Logical Access Boundaries",     "category": "Logical",   "caps": ["detection"]},
        {"id": "CC6.7",  "name": "Info Transmission Protection",  "category": "Logical",   "caps": ["ingestion"]},
        {"id": "CC6.8",  "name": "Malicious Software Prevention", "category": "Logical",   "caps": ["detection"]},
        {"id": "CC7.1",  "name": "System Vulnerability Detect",   "category": "Operations","caps": ["detection", "ioc_enrichment"]},
        {"id": "CC7.2",  "name": "Security Alerts Monitored",     "category": "Operations","caps": ["alerting", "detection"]},
        {"id": "CC7.3",  "name": "Security Events Evaluated",     "category": "Operations","caps": ["investigation", "correlation"]},
        {"id": "CC7.4",  "name": "Security Incidents Responded",  "category": "Operations","caps": ["case_management", "isolation"]},
        {"id": "CC7.5",  "name": "Identified Incidents Recovered","category": "Operations","caps": ["case_management"]},
        {"id": "CC8.1",  "name": "Change Management",             "category": "Change",    "caps": []},
        {"id": "CC9.1",  "name": "Risk Mitigation",               "category": "Risk",      "caps": ["investigation", "case_management"]},
        {"id": "A1.1",   "name": "Availability Monitoring",       "category": "Availability","caps": ["ingestion"]},
    ],
    "pci_dss": [
        {"id": "1.1",   "name": "Firewall Configuration",         "category": "Network",   "caps": []},
        {"id": "2.1",   "name": "Default Passwords Changed",      "category": "Config",    "caps": ["detection"]},
        {"id": "6.3",   "name": "Vulnerability Management",       "category": "Dev",       "caps": ["detection"]},
        {"id": "7.1",   "name": "Limit Access by Need",           "category": "Access",    "caps": ["detection", "ueba"]},
        {"id": "8.1",   "name": "User Identification & Auth",     "category": "Access",    "caps": ["detection"]},
        {"id": "8.6",   "name": "Authentication Mechanisms",      "category": "Access",    "caps": ["detection", "ueba"]},
        {"id": "10.1",  "name": "Audit Trail — Access",           "category": "Logging",   "caps": ["ingestion"]},
        {"id": "10.2",  "name": "Audit Trail — Events",           "category": "Logging",   "caps": ["ingestion", "detection"]},
        {"id": "10.3",  "name": "Secure Audit Trails",            "category": "Logging",   "caps": ["ingestion"]},
        {"id": "10.4",  "name": "Synchronized Clocks",            "category": "Logging",   "caps": []},
        {"id": "10.5",  "name": "Audit Trail Security",           "category": "Logging",   "caps": ["ingestion"]},
        {"id": "10.6",  "name": "Review Logs & Events",           "category": "Logging",   "caps": ["detection", "alerting"]},
        {"id": "10.7",  "name": "Retain Audit Logs 1yr",          "category": "Logging",   "caps": ["ingestion"]},
        {"id": "11.4",  "name": "IDS/IPS Monitoring",             "category": "Testing",   "caps": ["detection", "correlation"]},
        {"id": "11.5",  "name": "File Integrity Monitoring",      "category": "Testing",   "caps": ["detection"]},
        {"id": "12.10", "name": "Incident Response Plan",         "category": "Policy",    "caps": ["case_management", "alerting"]},
    ],
    "iso27001": [
        {"id": "A.6.1",  "name": "Org of Info Security",          "category": "Org",       "caps": []},
        {"id": "A.8.1",  "name": "Asset Management",              "category": "Asset",     "caps": ["ingestion"]},
        {"id": "A.9.1",  "name": "Access Control Policy",         "category": "Access",    "caps": ["detection"]},
        {"id": "A.9.2",  "name": "User Access Management",        "category": "Access",    "caps": ["detection", "ueba"]},
        {"id": "A.9.4",  "name": "System Access Control",         "category": "Access",    "caps": ["detection"]},
        {"id": "A.10.1", "name": "Cryptographic Controls",        "category": "Crypto",    "caps": []},
        {"id": "A.12.1", "name": "Operations Security",           "category": "Ops",       "caps": ["ingestion"]},
        {"id": "A.12.4", "name": "Logging & Monitoring",          "category": "Ops",       "caps": ["ingestion", "detection", "alerting"]},
        {"id": "A.12.6", "name": "Vulnerability Management",      "category": "Ops",       "caps": ["detection", "ioc_enrichment"]},
        {"id": "A.13.1", "name": "Network Security",              "category": "Network",   "caps": ["detection"]},
        {"id": "A.14.2", "name": "Security in Dev & Support",     "category": "Dev",       "caps": []},
        {"id": "A.16.1", "name": "Incident Management",           "category": "Incident",  "caps": ["detection", "alerting", "case_management"]},
        {"id": "A.16.2", "name": "Incident Reporting",            "category": "Incident",  "caps": ["alerting"]},
        {"id": "A.16.3", "name": "Incident Response",             "category": "Incident",  "caps": ["investigation", "isolation", "case_management"]},
        {"id": "A.18.1", "name": "Compliance with Legal Req",     "category": "Compliance","caps": []},
        {"id": "A.18.2", "name": "Info Security Reviews",         "category": "Compliance","caps": ["detection"]},
    ],
}

FRAMEWORK_META = {
    "nist_csf":  {"name": "NIST CSF",    "version": "1.1", "color": "#3fd68a"},
    "soc2":      {"name": "SOC 2 Type II","version": "2017","color": "#818cf8"},
    "pci_dss":   {"name": "PCI DSS",     "version": "4.0", "color": "#f97316"},
    "iso27001":  {"name": "ISO 27001",   "version": "2022","color": "#22d3ee"},
}


async def _active_capabilities(tenant_id: str) -> set[str]:
    """Determine which capabilities are active based on real data."""
    caps: set[str] = set()
    since = datetime.utcnow() - timedelta(days=30)

    events_col     = get_collection("events")
    detections_col = get_collection("detections")
    incidents_col  = get_collection("incidents")
    alerts_col     = get_collection("alerts")
    cases_col      = get_collection("cases")
    ioc_col        = get_collection("ioc_cache")
    blocked_col    = get_collection("blocked_entities")

    if await events_col.count_documents({"tenant_id": tenant_id, "timestamp": {"$gte": since}}):
        caps.add("ingestion")
    if await detections_col.count_documents({"tenant_id": tenant_id, "detected_at": {"$gte": since}}):
        caps.add("detection")
    if await incidents_col.count_documents({"tenant_id": tenant_id, "created_at": {"$gte": since}}):
        caps.add("correlation")
        caps.add("investigation")
    if await alerts_col.count_documents({"tenant_id": tenant_id, "sent_at": {"$gte": since}}):
        caps.add("alerting")
    if await cases_col.count_documents({"tenant_id": tenant_id}):
        caps.add("case_management")
    if await ioc_col.count_documents({"tenant_id": tenant_id}):
        caps.add("ioc_enrichment")
    if await blocked_col.count_documents({"tenant_id": tenant_id}):
        caps.add("isolation")

    # UEBA is always active once we have enough events
    event_count = await events_col.count_documents({"tenant_id": tenant_id})
    if event_count >= 10:
        caps.add("ueba")

    return caps


@router.get("/report/{framework}")
async def get_report(framework: str, request: Request, tenant_id: str = Depends(_resolve_tenant)):
    if framework not in FRAMEWORKS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown framework: {framework}")

    controls   = FRAMEWORKS[framework]
    active     = await _active_capabilities(tenant_id)
    meta       = FRAMEWORK_META[framework]

    results = []
    for ctrl in controls:
        required = ctrl["caps"]
        if not required:
            status = "manual"          # requires human process, not automated
        elif all(c in active for c in required):
            status = "covered"
        elif any(c in active for c in required):
            status = "partial"
        else:
            status = "gap"

        results.append({
            **ctrl,
            "status":          status,
            "active_caps":     [c for c in required if c in active],
            "missing_caps":    [c for c in required if c not in active],
        })

    covered  = sum(1 for r in results if r["status"] == "covered")
    partial  = sum(1 for r in results if r["status"] == "partial")
    manual   = sum(1 for r in results if r["status"] == "manual")
    gaps     = sum(1 for r in results if r["status"] == "gap")
    total    = len(results)
    score    = round((covered + partial * 0.5) / total * 100, 1) if total else 0

    categories: dict[str, list] = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    return {
        "framework":   framework,
        "meta":        meta,
        "score":       score,
        "summary":     {"covered": covered, "partial": partial, "manual": manual, "gaps": gaps, "total": total},
        "active_caps": sorted(active),
        "categories":  [{"name": k, "controls": v} for k, v in categories.items()],
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/report/{framework}/export", response_class=PlainTextResponse)
async def export_report(framework: str, request: Request, tenant_id: str = Depends(_resolve_tenant)):
    data = await get_report(framework, request, tenant_id)
    meta = data["meta"]
    s    = data["summary"]
    lines = [
        f"{'='*60}",
        f"  {meta['name']} v{meta['version']} Compliance Report",
        f"  Generated: {data['generated_at'][:19]} UTC",
        f"  Tenant: {tenant_id[:16]}…",
        f"{'='*60}",
        f"",
        f"OVERALL SCORE: {data['score']}%",
        f"  Covered : {s['covered']}/{s['total']}",
        f"  Partial : {s['partial']}/{s['total']}",
        f"  Manual  : {s['manual']}/{s['total']}",
        f"  Gaps    : {s['gaps']}/{s['total']}",
        f"",
        f"ACTIVE CAPABILITIES: {', '.join(data['active_caps']) or 'none'}",
        f"",
    ]
    for cat in data["categories"]:
        lines.append(f"── {cat['name'].upper()} {'─'*(40-len(cat['name']))}")
        for ctrl in cat["controls"]:
            icon = {"covered": "✓", "partial": "~", "manual": "M", "gap": "✗"}[ctrl["status"]]
            lines.append(f"  [{icon}] {ctrl['id']:<10} {ctrl['name']}")
            if ctrl["missing_caps"]:
                lines.append(f"          Missing: {', '.join(ctrl['missing_caps'])}")
        lines.append("")
    return "\n".join(lines)
