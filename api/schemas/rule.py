from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from api.models.alert import AlertSeverity
from api.models.rule import RuleType


class ThresholdConfig(BaseModel):
    source: Optional[str] = Field(None, description="Filter by source")
    event_type: Optional[str] = Field(None, description="Filter by event type")
    field: str = Field(..., description="Field to check (currently: 'count')")
    operator: str = Field(..., description="Comparison operator: >, <, >=, <=, ==")
    value: float = Field(..., description="Threshold value")
    window_minutes: int = Field(..., gt=0, le=1440, description="Time window in minutes (max 24h)")
    min_events: int = Field(1, ge=1, description="Minimum events required to evaluate")
    severity: AlertSeverity = Field(AlertSeverity.WARNING, description="Alert severity level")

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        allowed = [">", "<", ">=", "<=", "=="]
        if v not in allowed:
            raise ValueError(f"Operator must be one of {allowed}")
        return v

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        if v != "count":
            raise ValueError("Only 'count' field is supported")
        return v


class NumericValidation(BaseModel):
    expression: Optional[str] = Field(None, description="Math expression to evaluate")
    left_field: Optional[str] = Field(None, description="Left field for comparison")
    operator: str = Field(..., description="Comparison operator: <, <=, >, >=, ==, !=")
    threshold: Optional[float] = Field(None, description="Threshold value to compare against")
    right_field: Optional[str] = Field(None, description="Right field for field-to-field comparison")
    description: Optional[str] = Field(None, description="Human-readable description")

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        allowed = ["<", "<=", ">", ">=", "==", "!="]
        if v not in allowed:
            raise ValueError(f"operator must be one of {allowed}")
        return v

    def model_post_init(self, __context):
        if not self.expression and not self.left_field:
            raise ValueError("Either 'expression' or 'left_field' must be specified")
        if self.threshold is None and not self.right_field:
            raise ValueError("Either 'threshold' or 'right_field' must be specified")
        if self.expression and self.left_field:
            raise ValueError("Cannot specify both 'expression' and 'left_field'")
        if self.threshold is not None and self.right_field:
            raise ValueError("Cannot specify both 'threshold' and 'right_field'")


class FieldValidationConfig(BaseModel):
    source: Optional[str] = Field(None, description="Filter by source")
    event_type: str = Field(..., description="Event type to check (required)")
    required_fields: Optional[list[str]] = Field(
        None, min_length=1, description="Fields that must exist in event data"
    )
    allowed_values: Optional[dict[str, list[str]]] = Field(
        None, description="Map of field names to allowed values"
    )
    numeric_validations: Optional[list[NumericValidation]] = Field(
        None, description="List of numeric field validations"
    )
    alert_on_first: bool = Field(False, description="Alert immediately on first violation")
    severity: AlertSeverity = Field(AlertSeverity.WARNING, description="Alert severity level")

    @field_validator("allowed_values")
    @classmethod
    def validate_allowed_values(cls, v: dict[str, list[str]] | None) -> dict[str, list[str]] | None:
        if v is not None:
            for field, values in v.items():
                if not values:
                    raise ValueError(f"allowed_values for field '{field}' cannot be empty")
        return v

    def model_post_init(self, __context):
        if not self.required_fields and not self.allowed_values and not self.numeric_validations:
            raise ValueError(
                "At least one of 'required_fields', 'allowed_values', "
                "or 'numeric_validations' must be specified"
            )


class VolumeConfig(BaseModel):
    source: Optional[str] = Field(None, description="Filter by source")
    event_type: Optional[str] = Field(None, description="Filter by event type")
    comparison_window_hours: int = Field(
        24, ge=1, le=168, description="Comparison window (hours ago)"
    )
    current_window_minutes: int = Field(60, ge=5, le=1440, description="Current window to compare")
    threshold_percent: float = Field(
        ..., ge=-100, description="Percentage change threshold (-50 = 50% drop)"
    )
    min_baseline_events: int = Field(10, ge=1, description="Minimum baseline events required")
    severity: AlertSeverity = Field(AlertSeverity.CRITICAL, description="Alert severity level")


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    rule_type: RuleType = Field(..., description="Type of rule")
    config: dict[str, Any] = Field(..., description="Rule-specific configuration")
    is_active: bool = Field(True, description="Whether rule is active")
    tag: Optional[str] = Field(None, max_length=20, description="Optional tag")
    category: Optional[str] = Field(None, max_length=20, description="Optional category")

    @field_validator("config")
    @classmethod
    def validate_config(cls, v: dict[str, Any], info) -> dict[str, Any]:
        rule_type = info.data.get("rule_type")
        if rule_type == RuleType.THRESHOLD:
            ThresholdConfig(**v)
        elif rule_type == RuleType.FIELD_VALIDATION:
            FieldValidationConfig(**v)
        elif rule_type == RuleType.VOLUME:
            VolumeConfig(**v)
        return v


class RuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    tag: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=20)


class RuleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    rule_type: RuleType
    is_active: bool
    config: dict[str, Any]
    tag: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    updated_at: datetime
