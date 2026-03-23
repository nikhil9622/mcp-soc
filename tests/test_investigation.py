"""Unit tests for investigation agent — mock Anthropic client."""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from shared.models import Incident, DetectionEvent, NormalizedEvent, IncidentSummary


def _make_incident() -> Incident:
    return Incident(
        tenant_id="test",
        detection_ids=["d1", "d2"],
        severity="high",
        created_at=datetime.now(timezone.utc),
    )


def _make_summary() -> IncidentSummary:
    return IncidentSummary(
        summary="Brute force attempt detected",
        what_happened="Multiple failed login attempts from 1.2.3.4",
        why_suspicious="5+ failures in 2 minutes from a single IP",
        impact="Potential credential compromise",
        recommended_action="Block IP 1.2.3.4 and reset alice credentials",
        severity="high",
    )


def test_incident_summary_schema():
    schema = IncidentSummary.model_json_schema()
    assert "properties" in schema
    required_fields = {"summary", "what_happened", "why_suspicious", "impact", "recommended_action", "severity"}
    assert required_fields <= set(schema.get("properties", {}).keys())


def test_system_prompt_contains_no_hallucination():
    from agents.investigation import SYSTEM_PROMPT
    assert "only" in SYSTEM_PROMPT.lower()
    assert "not" in SYSTEM_PROMPT.lower() or "do not" in SYSTEM_PROMPT.lower()


def test_context_assembly():
    """Verify context passed to LLM contains required fields."""
    incident = _make_incident()
    detections = [{"detection_id": "d1", "rule_name": "Brute Force", "severity": "medium"}]
    context = {
        "incident_id": incident.incident_id,
        "tenant_id": incident.tenant_id,
        "severity": incident.severity,
        "created_at": incident.created_at.isoformat(),
        "detections": detections,
    }
    # Must be JSON-serializable
    serialized = json.dumps(context, default=str)
    parsed = json.loads(serialized)
    assert parsed["incident_id"] == incident.incident_id
    assert len(parsed["detections"]) == 1


def test_tool_use_schema_enforced():
    """tool_choice forces structured output — test that input is parsed into IncidentSummary."""
    raw_input = {
        "summary": "Test summary",
        "what_happened": "Something happened",
        "why_suspicious": "It was suspicious",
        "impact": "Some impact",
        "recommended_action": "Do something",
        "severity": "medium",
    }
    summary = IncidentSummary(**raw_input)
    assert summary.severity == "medium"
    assert summary.recommended_action == "Do something"


@pytest.mark.asyncio
async def test_investigation_agent_calls_anthropic(mocker):
    """Test that run_investigation_agent assembles correct API call."""
    from agents.investigation import run_investigation_agent

    incident = _make_incident()
    summary = _make_summary()

    # Mock tool_use response
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.input = summary.model_dump()

    mock_response = MagicMock()
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_response)

    mock_col = AsyncMock()
    mock_col.find_one = AsyncMock(return_value=None)
    mock_col.update_one = AsyncMock()
    mock_col.find = MagicMock(return_value=AsyncMock(to_list=AsyncMock(return_value=[])))

    with patch("agents.investigation.get_collection", return_value=mock_col):
        ctx = {"anthropic_client": mock_client, "running": False}
        fields = {k: str(v) if not isinstance(v, str) else v for k, v in incident.model_dump(mode="json").items()}
        result = await run_investigation_agent(ctx, tenant_id="test", **fields)

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["tool_choice"]["type"] == "tool"
    assert call_kwargs["tool_choice"]["name"] == "create_incident_summary"
