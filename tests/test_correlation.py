"""Unit tests for correlation agent graph logic."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from shared.models import DetectionEvent, NormalizedEvent


def _make_detection(detection_id: str, user: str, ip: str, severity: str = "medium") -> dict:
    event = NormalizedEvent(
        tenant_id="test",
        timestamp=datetime.now(timezone.utc),
        source="cloudtrail",
        user=user,
        ip=ip,
        action="ConsoleLogin",
    )
    det = DetectionEvent(
        detection_id=detection_id,
        tenant_id="test",
        event_id=event.event_id,
        rule_id="r1",
        rule_name="Test",
        mitre_technique_id="T1110",
        mitre_tactic="credential-access",
        severity=severity,
        risk_score=5.0,
        raw_event=event.model_dump(mode="json"),
    )
    return det.model_dump(mode="json")


def test_severity_order():
    from agents.correlation import SEVERITY_ORDER
    assert SEVERITY_ORDER["critical"] > SEVERITY_ORDER["high"]
    assert SEVERITY_ORDER["high"] > SEVERITY_ORDER["medium"]
    assert SEVERITY_ORDER["medium"] > SEVERITY_ORDER["low"]


def test_graph_connects_shared_user():
    import networkx as nx
    d1 = _make_detection("d1", user="alice", ip="1.2.3.4")
    d2 = _make_detection("d2", user="alice", ip="5.6.7.8")
    d3 = _make_detection("d3", user="bob", ip="9.9.9.9")

    G = nx.Graph()
    detections = [d1, d2, d3]
    for d in detections:
        G.add_node(d["detection_id"])

    for i, d1_ in enumerate(detections):
        for d2_ in detections[i + 1:]:
            e1 = d1_.get("raw_event", {})
            e2 = d2_.get("raw_event", {})
            if e1.get("user") and e1.get("user") == e2.get("user"):
                G.add_edge(d1_["detection_id"], d2_["detection_id"])

    components = list(nx.connected_components(G))
    # d1 and d2 share alice
    assert any({"d1", "d2"} <= c for c in components)
    # d3 (bob) is isolated
    assert any({"d3"} == c for c in components)


def test_minimum_two_detections():
    import networkx as nx
    # Single isolated node — should NOT form an incident
    d1 = _make_detection("d1", user="alice", ip="1.2.3.4")
    G = nx.Graph()
    G.add_node(d1["detection_id"])
    components = [c for c in nx.connected_components(G) if len(c) >= 2]
    assert len(components) == 0


def test_max_severity_calculation():
    from agents.correlation import SEVERITY_ORDER
    severities = ["medium", "high", "low"]
    max_sev = max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0))
    assert max_sev == "high"
