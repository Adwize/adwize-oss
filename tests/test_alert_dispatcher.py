import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.alert import Alert, AlertSeverity
from api.services.alert_dispatcher import (
    _build_base_payload,
    _format_payload,
    dispatch_webhook,
)


@pytest.fixture
def make_alert():
    def _make(
        severity=AlertSeverity.WARNING,
        message="Test alert fired",
        source="web",
        event_type="purchase",
        context=None,
    ):
        return Alert(
            id=uuid.uuid4(),
            rule_id=uuid.uuid4(),
            source=source,
            event_type=event_type,
            severity=severity,
            message=message,
            event_count=5,
            triggered_at=datetime.now(timezone.utc).replace(tzinfo=None),
            context=context or {},
        )

    return _make


@pytest.fixture
def db_mock():
    mock = AsyncMock(spec=AsyncSession)
    return mock


class TestPayloadFormatting:
    def test_slack_payload_structure(self, make_alert):
        alert = make_alert(severity=AlertSeverity.CRITICAL, message="Volume dropped!")
        payload = _build_base_payload(alert, "triggered")
        formatted = _format_payload(payload, "slack")

        assert "attachments" in formatted
        attachments = formatted["attachments"]
        assert len(attachments) == 1
        assert attachments[0]["color"] == "#D83B01"
        blocks = attachments[0]["blocks"]
        assert any("CRITICAL" in str(b) for b in blocks)

    def test_teams_payload_structure(self, make_alert):
        alert = make_alert(severity=AlertSeverity.WARNING, message="Field missing")
        payload = _build_base_payload(alert, "triggered")
        formatted = _format_payload(payload, "teams")

        assert formatted["@type"] == "MessageCard"
        assert formatted["themeColor"] == "FFB900"
        assert "Field missing" in formatted["text"]

    def test_generic_webhook_returns_raw_payload(self, make_alert):
        alert = make_alert()
        payload = _build_base_payload(alert, "triggered")
        formatted = _format_payload(payload, "webhook")

        assert formatted is payload

    def test_resolved_event_slack(self, make_alert):
        alert = make_alert()
        alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        payload = _build_base_payload(alert, "resolved")
        formatted = _format_payload(payload, "slack")

        assert formatted["attachments"][0]["color"] == "#36A64F"
        block_text = str(formatted["attachments"][0]["blocks"])
        assert "Resolved" in block_text

    def test_base_payload_fields(self, make_alert):
        alert = make_alert(severity=AlertSeverity.INFO, message="Test msg")
        payload = _build_base_payload(alert, "triggered")

        assert payload["event_type"] == "triggered"
        assert payload["alert_id"] == str(alert.id)
        assert payload["rule_id"] == str(alert.rule_id)
        assert payload["severity"] == "info"
        assert payload["message"] == "Test msg"
        assert payload["event_count"] == 5
        assert payload["triggered_at"] is not None
        assert payload["resolved_at"] is None

    def test_slack_severity_colors(self, make_alert):
        for sev, color in [
            (AlertSeverity.INFO, "#0078D4"),
            (AlertSeverity.WARNING, "#FFB900"),
            (AlertSeverity.CRITICAL, "#D83B01"),
        ]:
            alert = make_alert(severity=sev)
            payload = _build_base_payload(alert, "triggered")
            formatted = _format_payload(payload, "slack")
            assert formatted["attachments"][0]["color"] == color

    def test_teams_severity_colors(self, make_alert):
        for sev, color in [
            (AlertSeverity.INFO, "0078D4"),
            (AlertSeverity.WARNING, "FFB900"),
            (AlertSeverity.CRITICAL, "D83B01"),
        ]:
            alert = make_alert(severity=sev)
            payload = _build_base_payload(alert, "triggered")
            formatted = _format_payload(payload, "teams")
            assert formatted["themeColor"] == color


class TestDispatchWebhook:
    @pytest.mark.asyncio
    async def test_successful_delivery(self, make_alert, db_mock):
        import httpx

        alert = make_alert()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx, "AsyncClient", lambda **kwargs: mock_client)

            result = await dispatch_webhook(
                alert=alert,
                webhook_url="https://example.com/webhook",
                db=db_mock,
            )

        assert result is True
        db_mock.add.assert_called()
        db_mock.commit.assert_called()
