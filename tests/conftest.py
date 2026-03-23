import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from shared.models import NormalizedEvent, DetectionEvent, Incident


@pytest.fixture
def sample_event():
    return NormalizedEvent(
        tenant_id="tenant_test",
        timestamp=datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone.utc),
        source="cloudtrail",
        user="alice",
        user_type="IAMUser",
        ip="1.2.3.4",
        action="ConsoleLogin",
        country="US",
        is_new_location=False,
        metadata={"responseElements": {"ConsoleLogin": "Success"}},
    )


@pytest.fixture
def sample_detection(sample_event):
    return DetectionEvent(
        tenant_id="tenant_test",
        event_id=sample_event.event_id,
        rule_id="test-rule-id",
        rule_name="Test Rule",
        mitre_technique_id="T1110",
        mitre_tactic="credential-access",
        severity="medium",
        risk_score=5.0,
        raw_event=sample_event.model_dump(mode="json"),
    )


@pytest.fixture
def arq_ctx(mocker):
    ctx = {
        "running": False,
        "sigma_rules": [],
        "mitre_data": {},
    }
    return ctx


@pytest.fixture
def mock_mongo_col(mocker):
    col = AsyncMock()
    col.find_one = AsyncMock(return_value=None)
    col.insert_one = AsyncMock()
    col.update_one = AsyncMock()
    col.find = MagicMock(return_value=AsyncMock(to_list=AsyncMock(return_value=[])))
    return col
