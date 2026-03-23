"""MITRE ATT&CK coverage heatmap API."""
from __future__ import annotations
import json
from pathlib import Path
from functools import lru_cache
from fastapi import APIRouter, Depends
from db.mongo import get_collection
from api.dependencies import get_current_user

router = APIRouter(prefix="/mitre", tags=["mitre"])

TACTIC_ORDER = [
    "reconnaissance", "resource-development", "initial-access", "execution",
    "persistence", "privilege-escalation", "defense-evasion", "credential-access",
    "discovery", "lateral-movement", "collection", "command-and-control",
    "exfiltration", "impact",
]

TACTIC_LABELS = {
    "reconnaissance":      "Recon",
    "resource-development":"Resource Dev",
    "initial-access":      "Initial Access",
    "execution":           "Execution",
    "persistence":         "Persistence",
    "privilege-escalation":"Priv Esc",
    "defense-evasion":     "Def Evasion",
    "credential-access":   "Cred Access",
    "discovery":           "Discovery",
    "lateral-movement":    "Lateral Mvmt",
    "collection":          "Collection",
    "command-and-control": "C2",
    "exfiltration":        "Exfiltration",
    "impact":              "Impact",
}


@lru_cache(maxsize=1)
def _load_attack_data() -> dict:
    """Load enterprise-attack.json once and index by technique ID."""
    path = Path("data/enterprise-attack.json")
    if not path.exists():
        return {"tactics": {}, "techniques": {}}

    with open(path) as f:
        stix = json.load(f)

    objs = stix.get("objects", [])

    tactics: dict[str, str] = {}  # shortname → display name
    for o in objs:
        if o["type"] == "x-mitre-tactic":
            tactics[o["x_mitre_shortname"]] = o["name"]

    techniques: dict[str, dict] = {}  # T1234 → {name, tactics[]}
    for o in objs:
        if o["type"] != "attack-pattern":
            continue
        if o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        ext = next(
            (e for e in o.get("external_references", []) if e.get("source_name") == "mitre-attack"),
            None,
        )
        if not ext:
            continue
        tid = ext.get("external_id", "")
        if not tid.startswith("T") or "." in tid:  # skip sub-techniques
            continue
        phases = [
            p["phase_name"]
            for p in o.get("kill_chain_phases", [])
            if p.get("kill_chain_name") == "mitre-attack"
        ]
        techniques[tid] = {"name": o["name"], "tactics": phases}

    return {"tactics": tactics, "techniques": techniques}


@router.get("/coverage")
async def get_coverage(tenant_id: str = Depends(get_current_user)):
    """Return ATT&CK technique coverage grouped by tactic."""
    detections_col = get_collection("detections")

    # Count detections per technique for this tenant
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "mitre_technique_id": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$mitre_technique_id", "count": {"$sum": 1}, "severity": {"$max": "$severity"}}},
    ]
    rows = await detections_col.aggregate(pipeline).to_list(500)
    detected: dict[str, dict] = {r["_id"]: {"count": r["count"], "severity": r["severity"]} for r in rows}

    data = _load_attack_data()
    techniques = data["techniques"]

    # Build tactic buckets
    tactic_map: dict[str, list] = {t: [] for t in TACTIC_ORDER}

    for tid, meta in techniques.items():
        hit = detected.get(tid)
        entry = {
            "id":       tid,
            "name":     meta["name"],
            "count":    hit["count"] if hit else 0,
            "severity": hit["severity"] if hit else None,
            "detected": bool(hit),
        }
        for phase in meta["tactics"]:
            if phase in tactic_map:
                tactic_map[phase].append(entry)

    # Sort each tactic: detected first, then alphabetical
    for phase in tactic_map:
        tactic_map[phase].sort(key=lambda x: (-x["count"], x["name"]))

    tactics_out = []
    for phase in TACTIC_ORDER:
        techs = tactic_map.get(phase, [])
        tactics_out.append({
            "id":         phase,
            "name":       TACTIC_LABELS.get(phase, phase),
            "full_name":  data["tactics"].get(phase, phase),
            "techniques": techs,
            "detected":   sum(1 for t in techs if t["detected"]),
            "total":      len(techs),
        })

    total_techniques = len(techniques)
    total_detected   = len(detected)

    return {
        "tactics":          tactics_out,
        "total_techniques": total_techniques,
        "total_detected":   total_detected,
        "coverage_pct":     round(total_detected / total_techniques * 100, 1) if total_techniques else 0,
    }
