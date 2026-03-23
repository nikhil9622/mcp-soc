"""Attack Graph API — returns nodes and edges for visualization."""
from pathlib import Path
import yaml
from fastapi import APIRouter, Depends
from db.mongo import get_collection
from api.dependencies import get_current_user

router = APIRouter(prefix="/graph", tags=["graph"])

# Load rule titles from Sigma YAML files at startup
_RULE_TITLES: dict[str, str] = {}
_rules_dir = Path("detection_rules")
if _rules_dir.exists():
    for f in _rules_dir.glob("*.yaml"):
        try:
            r = yaml.safe_load(f.read_text())
            _RULE_TITLES[r.get("id", "")] = r.get("title", "")
        except Exception:
            pass


@router.get("/attack")
async def get_attack_graph(tenant_id: str = Depends(get_current_user)):
    incidents_col  = get_collection("incidents")
    detections_col = get_collection("detections")

    incidents  = await incidents_col.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(200)
    detections = await detections_col.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(500)

    # Index detections by rule_id for quick lookup
    rule_meta: dict[str, dict] = {}
    for d in detections:
        rid = d.get("rule_id", "")
        if rid and rid not in rule_meta:
            title = _RULE_TITLES.get(rid) or d.get("rule_title") or rid[:16] + "…"
            rule_meta[rid] = {
                "title": title,
                "mitre":    d.get("mitre_technique_id", ""),
                "severity": d.get("severity", "medium"),
            }

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(nid: str, label: str, ntype: str, severity: str = "medium", extra: dict = {}):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, "type": ntype,
                          "severity": severity, "incident_count": 0, **extra}
        nodes[nid]["incident_count"] += 1

    for inc in incidents:
        inc_id   = inc.get("incident_id", "")
        severity = inc.get("severity", "medium")
        entities = inc.get("entities", {})
        det_ids  = inc.get("detection_ids", [])

        # Collect rule nodes for this incident
        rule_nodes = set()
        for det in detections:
            if det.get("detection_id") in det_ids:
                rid = det.get("rule_id", "")
                if rid:
                    meta = rule_meta.get(rid, {})
                    mitre = meta.get("mitre", "")
                    label = meta.get("title", rid)[:30]
                    nid = f"rule:{rid}"
                    add_node(nid, label, "technique", meta.get("severity", severity),
                             {"mitre": mitre})
                    rule_nodes.add(nid)

        # User nodes
        for user in entities.get("users", []):
            nid = f"user:{user}"
            add_node(nid, user, "user", severity)
            for rnid in rule_nodes:
                edges.append({"source": nid, "target": rnid,
                              "incident_id": inc_id, "severity": severity})

        # IP nodes
        for ip in entities.get("ips", []):
            nid = f"ip:{ip}"
            add_node(nid, ip, "ip", severity)
            for rnid in rule_nodes:
                edges.append({"source": nid, "target": rnid,
                              "incident_id": inc_id, "severity": severity})

        # Connect users ↔ IPs
        for user in entities.get("users", []):
            for ip in entities.get("ips", []):
                edges.append({"source": f"user:{user}", "target": f"ip:{ip}",
                              "incident_id": inc_id, "severity": severity})

    # Deduplicate edges
    seen = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"])
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    return {
        "nodes": list(nodes.values()),
        "edges": unique_edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(unique_edges),
            "incidents": len(incidents),
        },
    }
