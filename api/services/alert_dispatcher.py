import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.logger import get_logger
from api.models.alert import Alert
from api.models.notification_log import NotificationLog

logger = get_logger(__name__)

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


async def dispatch_webhook(
    alert: Alert,
    webhook_url: str,
    db: AsyncSession,
    webhook_type: str = "webhook",
    event_type: str = "triggered",
    rule_name: str | None = None,
) -> bool:
    """Send alert notification to a webhook URL."""
    payload = _build_base_payload(alert, event_type)
    if rule_name:
        payload["rule_name"] = rule_name
    formatted_payload = _format_payload(payload, webhook_type)

    return await _send_webhook_with_retry(
        url=webhook_url,
        payload=formatted_payload,
        alert_id=alert.id,
        db=db,
        destination_type=webhook_type,
        max_retries=3,
        timeout=10,
    )


async def check_destination_cooldown(
    rule_id: uuid.UUID,
    destination_type: str,
    cooldown_minutes: int,
    db: AsyncSession,
) -> bool:
    """Return True if we can send (cooldown elapsed), False if still cooling down."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    threshold = now - timedelta(minutes=cooldown_minutes)

    query = (
        select(NotificationLog)
        .join(Alert, NotificationLog.alert_id == Alert.id, isouter=True)
        .where(
            NotificationLog.destination_type == destination_type,
            NotificationLog.delivered_at.is_not(None),
            NotificationLog.created_at >= threshold,
        )
    )
    query = query.where(
        (Alert.rule_id == rule_id) | (NotificationLog.alert_id.is_(None))
    )

    result = await db.execute(query.limit(1))
    recent = result.scalar_one_or_none()
    return recent is None


def _build_base_payload(alert: Alert, event_type: str) -> dict[str, Any]:
    severity_val = alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)

    return {
        "event_type": event_type,
        "alert_id": str(alert.id),
        "rule_id": str(alert.rule_id),
        "severity": severity_val,
        "message": alert.message,
        "event_count": alert.event_count,
        "context": alert.context,
        "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }


async def _send_webhook_with_retry(
    url: str,
    payload: dict[str, Any],
    alert_id: uuid.UUID | None,
    db: AsyncSession,
    destination_type: str,
    max_retries: int,
    timeout: int,
) -> bool:
    """Send webhook with retry logic and logging."""
    request_headers = {"Content-Type": "application/json"}

    for attempt in range(1, max_retries + 1):
        log_entry = NotificationLog(
            id=uuid.uuid4(),
            alert_id=alert_id,
            destination_type=destination_type,
            destination_url=url,
            payload=payload,
            attempts=attempt,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=request_headers)

                log_entry.status_code = response.status_code
                log_entry.response_body = response.text[:100]

                if 200 <= response.status_code < 300:
                    log_entry.delivered_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.add(log_entry)
                    await db.commit()
                    logger.info(f"Webhook delivered to {url} (attempt {attempt})")
                    return True
                else:
                    logger.warning(
                        f"Webhook to {url} failed with status {response.status_code} "
                        f"(attempt {attempt})"
                    )

        except httpx.TimeoutException:
            log_entry.response_body = f"Timeout after {timeout}s"
            logger.warning(f"Webhook to {url} timed out (attempt {attempt})")

        except Exception as e:
            log_entry.response_body = f"Error: {str(e)[:500]}"
            logger.error(f"Webhook to {url} failed: {e} (attempt {attempt})")

        db.add(log_entry)
        await db.commit()
        if attempt < max_retries:
            await asyncio.sleep(2**attempt)

    logger.error(f"Webhook to {url} failed after {max_retries} attempts")
    return False


def _format_payload(payload: dict[str, Any], format_type: str) -> dict[str, Any]:
    """Format payload for different webhook destinations."""
    if format_type == "slack":
        event_type = payload.get("event_type", "triggered")
        is_resolved = event_type == "resolved"

        config = {
            "triggered": {
                "emoji": ":rotating_light:",
                "title": f"{payload['severity'].upper()} Alert",
                "color": {"info": "#0078D4", "warning": "#FFB900", "critical": "#D83B01"}.get(
                    payload["severity"], "#808080"
                ),
            },
            "resolved": {
                "emoji": ":white_check_mark:",
                "title": "Alert Resolved",
                "color": "#36A64F",
            },
        }.get(event_type, {"emoji": ":bell:", "title": "Alert", "color": "#808080"})

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{config['emoji']} {config['title']}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{payload['message']}*"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{payload['severity'].upper()}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*{'Resolved' if is_resolved else 'Triggered'}:*\n{payload['resolved_at'] if is_resolved else payload['triggered_at']}",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Alert ID: `{payload['alert_id']}`"}],
            },
        ]

        return {"attachments": [{"color": config["color"], "blocks": blocks}]}

    elif format_type == "teams":
        theme_color = {
            "info": "0078D4",
            "warning": "FFB900",
            "critical": "D83B01",
        }

        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": payload["message"],
            "themeColor": theme_color.get(payload["severity"], "0078D4"),
            "title": f"Alert: {payload['severity'].upper()}",
            "text": payload["message"],
            "sections": [
                {
                    "facts": [
                        {"name": "Alert ID", "value": payload["alert_id"]},
                        {"name": "Event Count", "value": str(payload["event_count"])},
                        {"name": "Triggered", "value": payload["triggered_at"]},
                    ]
                }
            ],
        }

    else:
        return payload
