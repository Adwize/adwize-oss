import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import check_api_key
from api.config import get_settings
from api.database import get_db
from api.models.alert import Alert, AlertSeverity
from api.models.rule import Rule, RuleType
from api.schemas.alert import (
    AlertAcknowledge,
    AlertResolve,
    AlertResponse,
    AlertSnooze,
    GroupedAlertResponse,
    TestNotificationRequest,
)
from api.services.alert_dispatcher import dispatch_webhook

router = APIRouter()


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
    rule_id: uuid.UUID | None = Query(None),
    severity: AlertSeverity | None = Query(None),
    resolved: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[AlertResponse]:
    query = select(Alert, Rule.name.label("rule_name"), Rule.rule_type.label("rule_type")).join(
        Rule, Alert.rule_id == Rule.id, isouter=True
    )

    if rule_id:
        query = query.where(Alert.rule_id == rule_id)
    if severity:
        query = query.where(Alert.severity == severity)
    if resolved is not None:
        if resolved:
            query = query.where(Alert.resolved_at.is_not(None))
        else:
            query = query.where(Alert.resolved_at.is_(None))

    query = query.order_by(Alert.triggered_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.all()

    alerts = []
    for alert, rule_name, rule_type in rows:
        alert_dict = AlertResponse.model_validate(alert).model_dump()
        alert_dict["rule_name"] = rule_name
        alert_dict["rule_type"] = rule_type
        alerts.append(AlertResponse(**alert_dict))

    return alerts


@router.get("/grouped", response_model=list[GroupedAlertResponse])
async def list_grouped_alerts(
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    severity: AlertSeverity | None = Query(None),
    rule_type: RuleType | None = Query(None),
    source: str | None = Query(None),
    tag: str | None = Query(None, max_length=20),
    category: str | None = Query(None, max_length=20),
    limit: int = Query(50, ge=1, le=100),
) -> list[GroupedAlertResponse]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sparkline_start = now - timedelta(days=7)
    bucket_duration = timedelta(days=7) / 8

    query = select(
        Alert,
        Rule.name.label("rule_name"),
        Rule.rule_type.label("rule_type"),
        Rule.tag.label("rule_tag"),
        Rule.category.label("rule_category"),
    ).join(Rule, Alert.rule_id == Rule.id)

    if severity:
        query = query.where(Alert.severity == severity)
    if source:
        query = query.where(Alert.source == source)
    if rule_type:
        query = query.where(Rule.rule_type == rule_type)
    if tag:
        query = query.where(Rule.tag == tag)
    if category:
        query = query.where(Rule.category == category)

    query = query.order_by(Alert.triggered_at.desc())
    result = await db.execute(query)
    rows = result.all()

    grouped: dict[uuid.UUID, dict] = {}

    for alert, rule_name, r_type, rule_tag, rule_category in rows:
        key = alert.rule_id
        if key not in grouped:
            grouped[key] = {
                "rule_id": alert.rule_id,
                "rule_name": rule_name,
                "rule_type": r_type,
                "source": alert.source,
                "event_type": alert.event_type,
                "severity": alert.severity,
                "message": alert.message,
                "occurrence_count": 0,
                "total_event_count": 0,
                "first_seen": alert.triggered_at,
                "last_seen": alert.triggered_at,
                "active_count": 0,
                "acknowledged_count": 0,
                "resolved_count": 0,
                "alert_ids": [],
                "occurrence_history": [0] * 8,
                "tag": rule_tag,
                "category": rule_category,
            }

        g = grouped[key]
        g["occurrence_count"] += 1
        g["total_event_count"] += alert.event_count
        g["alert_ids"].append(alert.id)

        if alert.triggered_at < g["first_seen"]:
            g["first_seen"] = alert.triggered_at
        if alert.triggered_at > g["last_seen"]:
            g["last_seen"] = alert.triggered_at

        if alert.resolved_at:
            g["resolved_count"] += 1
        elif alert.acknowledged_at:
            g["acknowledged_count"] += 1
        else:
            g["active_count"] += 1

        if alert.triggered_at >= sparkline_start:
            time_since_start = (alert.triggered_at - sparkline_start).total_seconds()
            bucket_index = int(time_since_start / bucket_duration.total_seconds())
            if 0 <= bucket_index < 8:
                g["occurrence_history"][bucket_index] += 1

    result_list = []
    for g in grouped.values():
        if g["active_count"] > 0:
            g["status"] = "active"
        elif g["acknowledged_count"] > 0:
            g["status"] = "acknowledged"
        else:
            g["status"] = "resolved"

        if status_filter:
            if g["status"] != status_filter:
                continue

        result_list.append(GroupedAlertResponse(**g))

    result_list.sort(key=lambda x: x.last_seen, reverse=True)
    return result_list[:limit]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(
        select(Alert, Rule.name.label("rule_name"))
        .join(Rule, Alert.rule_id == Rule.id, isouter=True)
        .where(Alert.id == alert_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    alert, rule_name = row
    alert_dict = AlertResponse.model_validate(alert).model_dump()
    alert_dict["rule_name"] = rule_name
    return AlertResponse(**alert_dict)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    await db.delete(alert)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete alert: {str(e)}",
        )


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: uuid.UUID,
    resolve_data: AlertResolve,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found"
        )

    if alert.resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Alert is already resolved"
        )

    alert.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if resolve_data.note:
        alert.context["resolution_note"] = resolve_data.note

    try:
        await db.commit()
        await db.refresh(alert)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve alert: {str(e)}",
        )

    settings = get_settings()
    if settings.webhook_url:
        try:
            await dispatch_webhook(alert, settings.webhook_url, db, event_type="resolved")
        except Exception:
            pass

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    ack_data: AlertAcknowledge,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found"
        )

    if alert.acknowledged_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Alert is already acknowledged"
        )

    alert.acknowledged_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if ack_data.note:
        if alert.context is None:
            alert.context = {}
        alert.context["acknowledgment_note"] = ack_data.note

    try:
        await db.commit()
        await db.refresh(alert)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge alert: {str(e)}",
        )

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/snooze", response_model=AlertResponse)
async def snooze_alert(
    alert_id: uuid.UUID,
    snooze_data: AlertSnooze,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found"
        )

    if alert.resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot snooze a resolved alert"
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    alert.snoozed_until = now + timedelta(minutes=snooze_data.duration_minutes)

    try:
        await db.commit()
        await db.refresh(alert)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to snooze alert: {str(e)}",
        )

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/unsnooze", response_model=AlertResponse)
async def unsnooze_alert(
    alert_id: uuid.UUID,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found"
        )

    alert.snoozed_until = None

    try:
        await db.commit()
        await db.refresh(alert)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unsnooze alert: {str(e)}",
        )

    return AlertResponse.model_validate(alert)


@router.post("/test-notification", status_code=200)
async def send_test_notification(
    request: TestNotificationRequest,
    _auth: None = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
):
    test_alert = Alert(
        id=uuid.uuid4(),
        rule_id=uuid.UUID(int=0),
        source="test",
        event_type="test_notification",
        severity=AlertSeverity.INFO,
        message="This is a test alert from Adwize to verify your webhook setup.",
        event_count=42,
        context={"is_test": True},
        triggered_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    success = await dispatch_webhook(
        alert=test_alert,
        webhook_url=request.webhook_url,
        db=db,
        webhook_type=request.webhook_type,
        event_type="triggered",
        rule_name="Test Rule",
    )

    return {"success": success, "webhook_url": request.webhook_url}
