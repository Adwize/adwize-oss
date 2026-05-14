import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.alert import Alert, AlertSeverity


@pytest.fixture
def rule_id():
    return uuid.uuid4()


@pytest.fixture
def make_alert(rule_id):
    def _make(
        snoozed_until=None,
        resolved_at=None,
        severity=AlertSeverity.WARNING,
        rid=None,
    ):
        return Alert(
            id=uuid.uuid4(),
            rule_id=rid or rule_id,
            source="web",
            event_type="purchase",
            severity=severity,
            message="Test alert",
            event_count=5,
            triggered_at=datetime.now(timezone.utc).replace(tzinfo=None),
            snoozed_until=snoozed_until,
            resolved_at=resolved_at,
            context={},
        )
    return _make


class TestCheckSnoozed:
    async def test_not_snoozed_when_no_alerts(self):
        from worker.rule_monitoring import _check_snoozed

        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_result

        result = await _check_snoozed(uuid.uuid4(), db_mock)
        assert result is False

    async def test_snoozed_when_active_snooze_exists(self, make_alert, rule_id):
        from worker.rule_monitoring import _check_snoozed

        snoozed_alert = make_alert(
            snoozed_until=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2),
        )

        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = snoozed_alert
        db_mock.execute.return_value = mock_result

        result = await _check_snoozed(rule_id, db_mock)
        assert result is True

    async def test_not_snoozed_when_snooze_expired(self):
        from worker.rule_monitoring import _check_snoozed

        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_result

        result = await _check_snoozed(uuid.uuid4(), db_mock)
        assert result is False

    async def test_not_snoozed_when_alert_resolved(self):
        from worker.rule_monitoring import _check_snoozed

        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_result

        result = await _check_snoozed(uuid.uuid4(), db_mock)
        assert result is False


class TestSnoozeModel:
    async def test_snooze_sets_snoozed_until(self, make_alert):
        alert = make_alert()
        assert alert.snoozed_until is None

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        alert.snoozed_until = now + timedelta(minutes=240)

        assert alert.snoozed_until > now
        assert (alert.snoozed_until - now).total_seconds() == pytest.approx(240 * 60, abs=2)

    async def test_unsnooze_clears_snoozed_until(self, make_alert):
        alert = make_alert(
            snoozed_until=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=4)
        )
        assert alert.snoozed_until is not None

        alert.snoozed_until = None
        assert alert.snoozed_until is None

    async def test_cannot_snooze_resolved_alert(self, make_alert):
        alert = make_alert(
            resolved_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        assert alert.resolved_at is not None


class TestAlertSnoozeSchema:
    def test_valid_durations(self):
        from api.schemas.alert import AlertSnooze

        for mins in [15, 60, 240, 1440, 10080]:
            snooze = AlertSnooze(duration_minutes=mins)
            assert snooze.duration_minutes == mins

    def test_below_minimum_rejected(self):
        from api.schemas.alert import AlertSnooze

        with pytest.raises(Exception):
            AlertSnooze(duration_minutes=10)

    def test_above_maximum_rejected(self):
        from api.schemas.alert import AlertSnooze

        with pytest.raises(Exception):
            AlertSnooze(duration_minutes=20000)

    def test_zero_rejected(self):
        from api.schemas.alert import AlertSnooze

        with pytest.raises(Exception):
            AlertSnooze(duration_minutes=0)

    def test_negative_rejected(self):
        from api.schemas.alert import AlertSnooze

        with pytest.raises(Exception):
            AlertSnooze(duration_minutes=-60)
