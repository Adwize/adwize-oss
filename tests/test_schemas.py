"""Test Pydantic schema validation for rules and events."""

import pytest

from api.models.rule import RuleType
from api.schemas.event import EventBatch, EventData
from api.schemas.rule import (
    FieldValidationConfig,
    RuleCreate,
    ThresholdConfig,
    VolumeConfig,
)


class TestThresholdConfig:
    def test_valid_config(self):
        config = ThresholdConfig(
            event_type="error",
            field="count",
            operator=">",
            value=100,
            window_minutes=5,
        )
        assert config.operator == ">"
        assert config.window_minutes == 5

    def test_invalid_operator_rejected(self):
        with pytest.raises(Exception):
            ThresholdConfig(field="count", operator="~", value=100, window_minutes=5)

    def test_invalid_field_rejected(self):
        with pytest.raises(Exception):
            ThresholdConfig(field="invalid_field", operator=">", value=100, window_minutes=5)

    def test_zero_window_rejected(self):
        with pytest.raises(Exception):
            ThresholdConfig(field="count", operator=">", value=100, window_minutes=0)


class TestFieldValidationConfig:
    def test_valid_required_fields(self):
        config = FieldValidationConfig(
            event_type="purchase",
            required_fields=["user_id", "amount"],
        )
        assert config.required_fields == ["user_id", "amount"]

    def test_valid_allowed_values(self):
        config = FieldValidationConfig(
            event_type="purchase",
            allowed_values={"currency": ["USD", "EUR"]},
        )
        assert "currency" in config.allowed_values

    def test_empty_config_rejected(self):
        with pytest.raises(Exception):
            FieldValidationConfig(event_type="purchase")

    def test_empty_allowed_values_list_rejected(self):
        with pytest.raises(Exception):
            FieldValidationConfig(
                event_type="purchase",
                allowed_values={"currency": []},
            )


class TestVolumeConfig:
    def test_valid_config(self):
        config = VolumeConfig(threshold_percent=-50)
        assert config.threshold_percent == -50
        assert config.current_window_minutes == 60
        assert config.comparison_window_hours == 24

    def test_extreme_drop_allowed(self):
        config = VolumeConfig(threshold_percent=-100)
        assert config.threshold_percent == -100

    def test_positive_threshold_for_spike(self):
        config = VolumeConfig(threshold_percent=200)
        assert config.threshold_percent == 200


class TestRuleCreate:
    def test_threshold_rule_creation(self):
        rule = RuleCreate(
            name="High errors",
            rule_type=RuleType.THRESHOLD,
            config={
                "field": "count",
                "operator": ">",
                "value": 100,
                "window_minutes": 5,
            },
        )
        assert rule.name == "High errors"

    def test_field_validation_rule_creation(self):
        rule = RuleCreate(
            name="Purchase check",
            rule_type=RuleType.FIELD_VALIDATION,
            config={
                "event_type": "purchase",
                "required_fields": ["user_id", "amount"],
            },
        )
        assert rule.rule_type == RuleType.FIELD_VALIDATION

    def test_invalid_config_for_type_rejected(self):
        with pytest.raises(Exception):
            RuleCreate(
                name="Bad rule",
                rule_type=RuleType.THRESHOLD,
                config={"invalid_key": "value"},
            )

    def test_empty_name_rejected(self):
        with pytest.raises(Exception):
            RuleCreate(
                name="",
                rule_type=RuleType.THRESHOLD,
                config={"field": "count", "operator": ">", "value": 1, "window_minutes": 5},
            )


class TestEventSchemas:
    def test_event_data_minimal(self):
        event = EventData(type="page_view", data={"url": "/home"})
        assert event.type == "page_view"
        assert event.timestamp is None

    def test_event_batch_requires_events(self):
        with pytest.raises(Exception):
            EventBatch(source="web", events=[])

    def test_event_batch_valid(self):
        batch = EventBatch(
            source="web",
            events=[EventData(type="click", data={"button": "cta"})],
        )
        assert len(batch.events) == 1
        assert batch.source == "web"
