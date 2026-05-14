from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from api.models.alert import AlertSeverity
from api.models.rule import RuleType


class AlertResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    rule_id: UUID
    source: Optional[str] = None
    event_type: Optional[str] = None
    severity: AlertSeverity
    message: str
    event_count: int
    context: dict
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    rule_name: Optional[str] = None
    rule_type: Optional[RuleType] = None


class GroupedAlertResponse(BaseModel):
    rule_id: UUID
    rule_name: str
    rule_type: RuleType
    source: Optional[str] = None
    event_type: Optional[str] = None
    severity: AlertSeverity
    message: str
    occurrence_count: int
    total_event_count: int
    first_seen: datetime
    last_seen: datetime
    status: str
    active_count: int
    acknowledged_count: int
    resolved_count: int
    alert_ids: list[UUID]
    occurrence_history: list[int] = []
    tag: Optional[str] = None
    category: Optional[str] = None


class AlertAcknowledge(BaseModel):
    note: Optional[str] = Field(None, max_length=500, description="Acknowledgment note")


class AlertResolve(BaseModel):
    note: Optional[str] = Field(None, max_length=500, description="Resolution note")


class AlertSnooze(BaseModel):
    duration_minutes: int = Field(
        ..., ge=15, le=10080, description="Snooze duration in minutes (15 min to 7 days)"
    )


class TestNotificationRequest(BaseModel):
    webhook_url: str = Field(..., description="Webhook URL to send test notification to")
    webhook_type: str = Field("webhook", description="Type: slack | teams | webhook")
