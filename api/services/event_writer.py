import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.event import Event


def normalize_timestamp(ts: datetime | int | float | str | None) -> datetime:
    """Convert any supported timestamp format to a timezone-naive UTC datetime."""
    if ts is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            return ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts

    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(tzinfo=None)

    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError):
        return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_event(
    *,
    source: str,
    event_type: str,
    event_data: Any,
    timestamp: datetime | int | float | str | None = None,
) -> dict:
    """Build a row dict ready for bulk insertion into the events table."""
    return {
        "id": uuid.uuid4(),
        "source": source,
        "event_type": event_type,
        "event_data": event_data if isinstance(event_data, dict) else {"raw": event_data},
        "received_at": normalize_timestamp(timestamp),
    }


async def bulk_insert_events(session: AsyncSession, rows: list[dict]) -> int:
    """Insert multiple event rows in a single multi-row INSERT statement."""
    if not rows:
        return 0
    stmt = pg_insert(Event).values(rows)
    await session.execute(stmt)
    await session.commit()
    return len(rows)
