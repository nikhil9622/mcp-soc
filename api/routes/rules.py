"""Detection rules endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pathlib import Path
import yaml
import json

from db.mongo import get_collection
from api.dependencies import get_current_user_api_key

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("")
async def list_rules(
    tenant_id: str = Depends(get_current_user_api_key),
    skip: int = 0,
    limit: int = 50,
):
    """
    List all detection rules.
    
    Returns Sigma rule metadata for the tenant.
    """
    rules = []
    rules_dir = Path("detection_rules")
    
    if not rules_dir.exists():
        return []
    
    for rule_file in sorted(rules_dir.glob("*.yaml"))[:limit]:
        try:
            with open(rule_file) as f:
                rule_data = yaml.safe_load(f)
                rules.append({
                    "rule_id": rule_data.get("id", rule_file.stem),
                    "title": rule_data.get("title", "Unknown"),
                    "description": rule_data.get("description", ""),
                    "severity": rule_data.get("level", "medium"),
                    "mitre_techniques": rule_data.get("tags", {}).get("mitre_attack.t", []),
                    "file": rule_file.name,
                })
        except Exception as e:
            continue  # Skip malformed rules
    
    return rules


@router.get("/{rule_id}")
async def get_rule(
    rule_id: str,
    tenant_id: str = Depends(get_current_user_api_key),
):
    """Get full rule details."""
    rules_dir = Path("detection_rules")
    
    # Try to find rule by ID or filename
    for rule_file in rules_dir.glob("*.yaml"):
        try:
            with open(rule_file) as f:
                rule_data = yaml.safe_load(f)
                if rule_data.get("id") == rule_id or rule_file.stem == rule_id:
                    return {
                        "rule_id": rule_data.get("id", rule_file.stem),
                        "title": rule_data.get("title"),
                        "description": rule_data.get("description"),
                        "severity": rule_data.get("level"),
                        "detection": rule_data.get("detection"),
                        "mitre_techniques": rule_data.get("tags", {}).get("mitre_attack.t", []),
                        "mitre_tactics": rule_data.get("tags", {}).get("mitre_attack.tactic", []),
                        "file": rule_file.name,
                    }
        except Exception:
            continue
    
    raise HTTPException(status_code=404, detail="Rule not found")


@router.get("/{rule_id}/stats")
async def get_rule_stats(
    rule_id: str,
    tenant_id: str = Depends(get_current_user_api_key),
):
    """Get rule performance statistics."""
    detections_col = get_collection("detections")
    
    # Count detections for this rule
    total = await detections_col.count_documents({
        "tenant_id": tenant_id,
        "rule_name": rule_id,
    })
    
    by_severity = {}
    for severity in ["critical", "high", "medium", "low"]:
        count = await detections_col.count_documents({
            "tenant_id": tenant_id,
            "rule_name": rule_id,
            "severity": severity,
        })
        by_severity[severity] = count
    
    # Get TP/FP feedback stats (from alerts)
    alerts_col = get_collection("alerts")
    tp_count = await alerts_col.count_documents({
        "tenant_id": tenant_id,
        "feedback": "tp",
    })
    fp_count = await alerts_col.count_documents({
        "tenant_id": tenant_id,
        "feedback": "fp",
    })
    
    total_feedback = tp_count + fp_count
    tp_rate = (tp_count / total_feedback * 100) if total_feedback > 0 else 0
    
    return {
        "rule_id": rule_id,
        "total_detections": total,
        "by_severity": by_severity,
        "feedback": {
            "tp": tp_count,
            "fp": fp_count,
            "tp_rate": f"{tp_rate:.1f}%",
        },
    }
