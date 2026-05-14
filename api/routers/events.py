import asyncio
import json as json_mod
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import check_api_key
from api.database import get_db
from api.models.event import Event
from api.schemas.event import EventBatch, EventCreate, EventResponse
from api.services.event_writer import bulk_insert_events, normalize_event

router = APIRouter()


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def ingest_events(
    batch: EventBatch,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    rows = [
        normalize_event(
            source=batch.source,
            event_type=event_data.type,
            event_data=event_data.data,
            timestamp=event_data.timestamp,
        )
        for event_data in batch.events
    ]

    try:
        await bulk_insert_events(db, rows)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store events: {str(e)}",
        )

    created_events = [
        EventCreate(
            id=row["id"],
            source=row["source"],
            event_type=row["event_type"],
            received_at=row["received_at"],
        )
        for row in rows
    ]

    return EventResponse(
        success=True,
        events_received=len(created_events),
        events=created_events,
    )


@router.get("/events/")
async def list_events(
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source: str | None = None,
    event_type: str | None = None,
    search: str | None = Query(default=None, description="Full-text search in event payloads"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    properties: str | None = Query(default=None, description="JSON key-value pairs to match"),
    include_count: bool = False,
) -> dict:
    filters = []

    if source:
        filters.append(Event.source == source)
    if event_type:
        filters.append(Event.event_type == event_type)
    if search:
        filters.append(cast(Event.event_data, Text).ilike(f"%{search}%"))
    if start_date:
        naive_start = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        filters.append(Event.received_at >= naive_start)
    if end_date:
        naive_end = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
        filters.append(Event.received_at <= naive_end)
    if properties:
        try:
            prop_dict = json_mod.loads(properties)
            if isinstance(prop_dict, dict):
                filters.append(Event.event_data.contains(prop_dict))
        except (json_mod.JSONDecodeError, ValueError):
            pass

    query = (
        select(Event)
        .where(*filters)
        .order_by(Event.received_at.desc())
        .limit(min(limit, 100))
        .offset(offset)
    )
    result = await db.execute(query)
    events = result.scalars().all()

    total = None
    if include_count:
        count_query = select(func.count()).select_from(Event).where(*filters)
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

    effective_limit = min(limit, 100)
    if total is not None:
        has_more = (offset + len(events)) < total
    else:
        has_more = len(events) == effective_limit

    return {
        "events": [
            {
                "id": str(e.id),
                "source": e.source,
                "event_type": e.event_type,
                "event_data": e.event_data,
                "received_at": e.received_at.isoformat() if e.received_at else None,
            }
            for e in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@router.get("/events/stats")
async def get_event_stats(
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
    source: str | None = Query(default=None),
) -> dict:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

    base_filters = [Event.received_at >= cutoff]
    if source:
        base_filters.append(Event.source == source)

    by_type_q = (
        select(Event.event_type, func.count().label("count"))
        .where(*base_filters)
        .group_by(Event.event_type)
        .order_by(func.count().desc())
    )
    by_source_q = (
        select(Event.source, func.count().label("count"))
        .where(*base_filters)
        .group_by(Event.source)
        .order_by(func.count().desc())
    )

    type_result = await db.execute(by_type_q)
    source_result = await db.execute(by_source_q)

    by_type = [{"event_type": row[0], "count": row[1]} for row in type_result.fetchall()]
    by_source = [{"source": row[0], "count": row[1]} for row in source_result.fetchall()]
    total = sum(item["count"] for item in by_type)

    return {
        "total_events_24h": total,
        "by_event_type": by_type,
        "by_source": by_source,
    }


@router.get("/events/stream")
async def stream_events(
    request: Request,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
    source: str | None = None,
    event_type: str | None = None,
) -> StreamingResponse:
    """SSE endpoint for live tail mode."""
    from api.database import AsyncSessionLocal

    async def event_generator():
        last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
        while True:
            if await request.is_disconnected():
                break

            async with AsyncSessionLocal() as session:
                query = select(Event).where(Event.received_at > last_seen)
                if source:
                    query = query.where(Event.source == source)
                if event_type:
                    query = query.where(Event.event_type == event_type)

                query = query.order_by(Event.received_at.asc()).limit(50)
                result = await session.execute(query)
                new_events = result.scalars().all()

                for e in new_events:
                    data = json_mod.dumps(
                        {
                            "id": str(e.id),
                            "source": e.source,
                            "event_type": e.event_type,
                            "event_data": e.event_data,
                            "received_at": e.received_at.isoformat() if e.received_at else None,
                        }
                    )
                    yield f"data: {data}\n\n"
                    if e.received_at and e.received_at > last_seen:
                        last_seen = e.received_at

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
