import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.alert import Alert, AlertSeverity
from api.models.event import Event
from api.models.rule import Rule, RuleType
from api.services.rule_engine import (
    check_should_create_alert,
    evaluate_field_validation_rule,
    evaluate_threshold_rule,
    evaluate_volume_rule,
)


@pytest.fixture
def sample_rule_field_validation():
    return Rule(
        id=uuid.uuid4(),
        name="Test Field Validation Rule",
        rule_type=RuleType.FIELD_VALIDATION,
        is_active=True,
        config={
            "event_type": "purchase",
            "required_fields": ["transaction_id", "amount"],
            "severity": "critical",
        },
    )


@pytest.fixture
def sample_rule_allowed_values():
    return Rule(
        id=uuid.uuid4(),
        name="Test Allowed Values Rule",
        rule_type=RuleType.FIELD_VALIDATION,
        is_active=True,
        config={
            "event_type": "page_view",
            "allowed_values": {"referrer": ["google", "facebook", "tiktok"]},
            "severity": "warning",
        },
    )


@pytest.fixture
def sample_rule_threshold():
    return Rule(
        id=uuid.uuid4(),
        name="Test Threshold Rule",
        rule_type=RuleType.THRESHOLD,
        is_active=True,
        config={
            "event_type": "payment_failed",
            "field": "count",
            "operator": ">",
            "value": 10,
            "window_minutes": 60,
            "severity": "warning",
        },
    )


@pytest.fixture
def sample_rule_volume():
    return Rule(
        id=uuid.uuid4(),
        name="Test Volume Rule",
        rule_type=RuleType.VOLUME,
        is_active=True,
        config={
            "event_type": "purchase",
            "threshold_percent": -50,
            "current_window_minutes": 60,
            "comparison_window_hours": 24,
            "min_baseline_events": 10,
            "severity": "critical",
        },
    )


@pytest.fixture
def sample_event_with_missing_fields():
    return Event(
        id=uuid.uuid4(),
        source="web",
        event_type="purchase",
        event_data={"product_id": "123"},
        received_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


@pytest.fixture
def sample_event_complete():
    return Event(
        id=uuid.uuid4(),
        source="web",
        event_type="purchase",
        event_data={
            "product_id": "123",
            "transaction_id": "txn_123",
            "amount": 99.99,
        },
        received_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


class TestFieldValidationRule:
    async def test_missing_fields_creates_alert(
        self, sample_rule_field_validation, sample_event_with_missing_fields
    ):
        db_mock = AsyncMock(spec=AsyncSession)

        alert = await evaluate_field_validation_rule(
            sample_rule_field_validation, sample_event_with_missing_fields, db_mock
        )

        assert alert is not None
        assert alert.rule_id == sample_rule_field_validation.id
        assert alert.severity == AlertSeverity.CRITICAL
        assert "transaction_id" in alert.message
        assert "amount" in alert.message
        assert alert.source == "web"
        assert alert.event_type == "purchase"
        assert "transaction_id" in alert.context["missing_fields"]
        assert "amount" in alert.context["missing_fields"]

    async def test_no_alert_when_fields_complete(
        self, sample_rule_field_validation, sample_event_complete
    ):
        db_mock = AsyncMock(spec=AsyncSession)

        alert = await evaluate_field_validation_rule(
            sample_rule_field_validation, sample_event_complete, db_mock
        )

        assert alert is None

    async def test_filters_by_source(
        self, sample_rule_field_validation, sample_event_with_missing_fields
    ):
        db_mock = AsyncMock(spec=AsyncSession)
        sample_rule_field_validation.config["source"] = "mobile"

        alert = await evaluate_field_validation_rule(
            sample_rule_field_validation, sample_event_with_missing_fields, db_mock
        )

        assert alert is None

    async def test_filters_by_event_type(
        self, sample_rule_field_validation, sample_event_with_missing_fields
    ):
        db_mock = AsyncMock(spec=AsyncSession)
        sample_event_with_missing_fields.event_type = "page_view"

        alert = await evaluate_field_validation_rule(
            sample_rule_field_validation, sample_event_with_missing_fields, db_mock
        )

        assert alert is None

    async def test_null_values_treated_as_missing(self, sample_rule_field_validation):
        db_mock = AsyncMock(spec=AsyncSession)

        event = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"transaction_id": None, "amount": 99.99},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        alert = await evaluate_field_validation_rule(sample_rule_field_validation, event, db_mock)

        assert alert is not None
        assert "transaction_id" in alert.context["missing_fields"]

    async def test_allowed_values_invalid(self, sample_rule_allowed_values):
        db_mock = AsyncMock(spec=AsyncSession)

        event = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="page_view",
            event_data={"page": "/pricing", "referrer": "twitter"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        alert = await evaluate_field_validation_rule(sample_rule_allowed_values, event, db_mock)

        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "referrer" in alert.message
        assert "twitter" in alert.message
        assert alert.context["invalid_values"]["referrer"]["actual"] == "twitter"

    async def test_allowed_values_valid(self, sample_rule_allowed_values):
        db_mock = AsyncMock(spec=AsyncSession)

        event = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="page_view",
            event_data={"page": "/pricing", "referrer": "google"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        alert = await evaluate_field_validation_rule(sample_rule_allowed_values, event, db_mock)

        assert alert is None

    async def test_combined_validations(self, sample_rule_field_validation):
        db_mock = AsyncMock(spec=AsyncSession)
        sample_rule_field_validation.config["allowed_values"] = {"status": ["active", "pending"]}

        event = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"product_id": "123", "status": "invalid"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        alert = await evaluate_field_validation_rule(sample_rule_field_validation, event, db_mock)

        assert alert is not None
        assert "transaction_id" in alert.context["missing_fields"]
        assert "amount" in alert.context["missing_fields"]
        assert alert.context["invalid_values"]["status"]["actual"] == "invalid"


class TestThresholdRule:
    @pytest.mark.parametrize(
        "event_count,should_alert",
        [
            (15, True),
            (10, False),
            (5, False),
            (0, False),
        ],
    )
    async def test_threshold_greater_than(self, sample_rule_threshold, event_count, should_alert):
        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar_one.return_value = event_count
        db_mock.execute.return_value = mock_result

        alert = await evaluate_threshold_rule(sample_rule_threshold, db_mock)

        if should_alert:
            assert alert is not None
            assert alert.rule_id == sample_rule_threshold.id
            assert alert.severity == AlertSeverity.WARNING
            assert str(event_count) in alert.message
            assert alert.event_count == event_count
        else:
            assert alert is None

    @pytest.mark.parametrize(
        "event_count,should_alert",
        [
            (0, True),
            (3, True),
            (4, True),
            (5, False),
            (10, False),
        ],
    )
    async def test_threshold_less_than_with_zero_events(self, event_count, should_alert):
        """Verifies the '<' operator alerts even on 0 events."""
        rule = Rule(
            id=uuid.uuid4(),
            name="Low purchase alert",
            rule_type=RuleType.THRESHOLD,
            is_active=True,
            config={
                "field": "count",
                "value": 5,
                "operator": "<",
                "severity": "warning",
                "event_type": "purchase",
                "window_minutes": 60,
            },
        )

        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar_one.return_value = event_count
        db_mock.execute.return_value = mock_result

        alert = await evaluate_threshold_rule(rule, db_mock)

        if should_alert:
            assert alert is not None, f"Expected alert for {event_count} < 5"
            assert alert.rule_id == rule.id
            assert alert.event_count == event_count
        else:
            assert alert is None, f"Did not expect alert for {event_count} < 5"

    async def test_threshold_less_than_or_equal_with_zero_events(self):
        rule = Rule(
            id=uuid.uuid4(),
            name="Low or no purchase alert",
            rule_type=RuleType.THRESHOLD,
            is_active=True,
            config={
                "field": "count",
                "value": 5,
                "operator": "<=",
                "severity": "critical",
                "event_type": "purchase",
                "window_minutes": 60,
            },
        )

        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar_one.return_value = 0
        db_mock.execute.return_value = mock_result

        alert = await evaluate_threshold_rule(rule, db_mock)

        assert alert is not None, "Should alert when 0 <= 5"
        assert alert.event_count == 0


class TestVolumeRule:
    @pytest.mark.parametrize(
        "current_count,baseline_count,should_alert,expected_message",
        [
            (10, 100, True, "dropped"),
            (5, 5, False, None),
            (100, 10, False, None),
        ],
    )
    async def test_volume_rule(
        self,
        sample_rule_volume,
        current_count,
        baseline_count,
        should_alert,
        expected_message,
    ):
        db_mock = AsyncMock(spec=AsyncSession)
        mock_current = Mock()
        mock_current.scalar_one.return_value = current_count
        mock_baseline = Mock()
        mock_baseline.scalar_one.return_value = baseline_count

        db_mock.execute.side_effect = [mock_current, mock_baseline]

        alert = await evaluate_volume_rule(sample_rule_volume, db_mock)

        if should_alert:
            assert alert is not None
            assert alert.rule_id == sample_rule_volume.id
            assert alert.severity == AlertSeverity.CRITICAL
            if expected_message:
                assert expected_message in alert.message.lower()
            assert alert.context["current_count"] == current_count
            assert alert.context["baseline_count"] == baseline_count
        else:
            assert alert is None


class TestDebouncing:
    @pytest.mark.parametrize(
        "minutes_ago,should_create",
        [
            (None, True),
            (30, False),
            (70, True),
        ],
    )
    async def test_check_should_create_alert(self, minutes_ago, should_create):
        db_mock = AsyncMock(spec=AsyncSession)
        mock_result = Mock()

        if minutes_ago is None or minutes_ago > 60:
            mock_result.scalar_one_or_none.return_value = None
        else:
            recent_alert = Alert(
                id=uuid.uuid4(),
                rule_id=uuid.uuid4(),
                source="web",
                event_type="purchase",
                severity=AlertSeverity.WARNING,
                message="Test",
                event_count=1,
                triggered_at=datetime.now(timezone.utc).replace(tzinfo=None)
                - timedelta(minutes=minutes_ago),
            )
            mock_result.scalar_one_or_none.return_value = recent_alert

        db_mock.execute.return_value = mock_result

        result = await check_should_create_alert(uuid.uuid4(), "web", "purchase", db_mock)

        assert result is should_create


class TestNumericValidations:
    @pytest.mark.asyncio
    async def test_expression_greater_than(self):
        rule = Rule(
            id=uuid.uuid4(),
            name="Average item value check",
            rule_type=RuleType.FIELD_VALIDATION,
            is_active=True,
            config={
                "event_type": "purchase",
                "numeric_validations": [
                    {
                        "expression": "value / items",
                        "operator": ">",
                        "threshold": 10,
                        "description": "Average item value must be greater than 10",
                    }
                ],
                "severity": "warning",
            },
        )

        db_mock = AsyncMock(spec=AsyncSession)

        event_pass = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"value": 100, "items": 5},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        alert = await evaluate_field_validation_rule(rule, event_pass, db_mock)
        assert alert is None

        event_fail = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"value": 50, "items": 10},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        alert = await evaluate_field_validation_rule(rule, event_fail, db_mock)
        assert alert is not None
        assert "Numeric validation failed" in alert.message
        assert "value / items" in alert.message

    @pytest.mark.asyncio
    async def test_field_comparison(self):
        rule = Rule(
            id=uuid.uuid4(),
            name="Discount validation",
            rule_type=RuleType.FIELD_VALIDATION,
            is_active=True,
            config={
                "event_type": "add_to_cart",
                "numeric_validations": [
                    {
                        "left_field": "discount",
                        "operator": "<",
                        "right_field": "amount",
                        "description": "Discount must be less than amount",
                    }
                ],
                "severity": "critical",
            },
        )

        db_mock = AsyncMock(spec=AsyncSession)

        event_pass = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="add_to_cart",
            event_data={"discount": 10, "amount": 100},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        alert = await evaluate_field_validation_rule(rule, event_pass, db_mock)
        assert alert is None

        event_fail = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="add_to_cart",
            event_data={"discount": 150, "amount": 100},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        alert = await evaluate_field_validation_rule(rule, event_fail, db_mock)
        assert alert is not None
        assert "discount" in alert.message
        assert "amount" in alert.message

    @pytest.mark.asyncio
    async def test_combined_numeric_and_allowed_values(self):
        rule = Rule(
            id=uuid.uuid4(),
            name="Combined validation",
            rule_type=RuleType.FIELD_VALIDATION,
            is_active=True,
            config={
                "severity": "warning",
                "event_type": "purchase",
                "allowed_values": {"currency": ["USD", "EUR"]},
                "numeric_validations": [
                    {
                        "left_field": "value",
                        "operator": ">",
                        "threshold": 0,
                        "description": "Value must be positive",
                    }
                ],
            },
        )

        db_mock = AsyncMock(spec=AsyncSession)

        event_pass = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"value": 100, "currency": "USD"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        assert await evaluate_field_validation_rule(rule, event_pass, db_mock) is None

        event_fail_currency = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"value": 100, "currency": "GBP"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        alert = await evaluate_field_validation_rule(rule, event_fail_currency, db_mock)
        assert alert is not None
        assert "currency" in alert.message

        event_fail_value = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"value": 0, "currency": "USD"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        alert = await evaluate_field_validation_rule(rule, event_fail_value, db_mock)
        assert alert is not None
        assert "Numeric validation failed" in alert.message

        event_fail_both = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="purchase",
            event_data={"value": -10, "currency": "GBP"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        alert = await evaluate_field_validation_rule(rule, event_fail_both, db_mock)
        assert alert is not None
        assert "currency" in alert.message
        assert "Numeric validation failed" in alert.message

    @pytest.mark.asyncio
    async def test_ignores_non_matching_event_type(self):
        rule = Rule(
            id=uuid.uuid4(),
            name="Purchase currency validation",
            rule_type=RuleType.FIELD_VALIDATION,
            is_active=True,
            config={
                "severity": "info",
                "event_type": "purchase",
                "allowed_values": {"currency": ["USD"]},
            },
        )

        db_mock = AsyncMock(spec=AsyncSession)

        event = Event(
            id=uuid.uuid4(),
            source="web",
            event_type="page_view",
            event_data={"value": 100, "currency": "EUR"},
            received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        alert = await evaluate_field_validation_rule(rule, event, db_mock)
        assert alert is None
