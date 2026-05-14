from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventData(BaseModel):
    id: str | None = Field(default=None, description="Event ID")
    type: str = Field(..., description="Event type")
    timestamp: datetime | None = Field(default=None, description="Event timestamp")
    data: dict[str, Any] = Field(..., description="Event payload data")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional metadata")


class EventBatch(BaseModel):
    source: str = Field(..., description="Source type")
    source_id: str | None = Field(default=None, description="Source identifier")
    events: list[EventData] = Field(..., min_length=1, description="List of events")


class EventCreate(BaseModel):
    id: UUID
    source: str
    event_type: str
    received_at: datetime


class EventResponse(BaseModel):
    success: bool
    events_received: int
    events: list[EventCreate]
