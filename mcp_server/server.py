"""Adwize MCP Server — exposes event monitoring tools to AI assistants."""

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Adwize",
    instructions="Monitor analytics events, manage rules, and inspect alerts via Adwize API.",
)

API_BASE = os.getenv("ADWIZE_API_URL", "http://localhost:8000").rstrip("/")
API_PREFIX = f"{API_BASE}/api/v1"


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("ADWIZE_API_KEY")
    if api_key:
        headers["X-Api-Key"] = api_key
    return headers


def _client() -> httpx.Client:
    return httpx.Client(headers=_headers(), timeout=30)


@mcp.tool()
def list_events(
    source: str | None = None,
    event_type: str | None = None,
    limit: int = 20,
) -> str:
    """List recent events from the Adwize event stream.

    Args:
        source: Filter by event source (e.g. 'web', 'mobile')
        event_type: Filter by event type (e.g. 'page_view', 'purchase')
        limit: Number of events to return (max 100)
    """
    params: dict = {"limit": min(limit, 100)}
    if source:
        params["source"] = source
    if event_type:
        params["event_type"] = event_type

    with _client() as client:
        resp = client.get(f"{API_PREFIX}/events/", params=params)
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def get_event_stats(source: str | None = None) -> str:
    """Get event statistics for the last 24 hours.

    Args:
        source: Optional source filter
    """
    params = {}
    if source:
        params["source"] = source

    with _client() as client:
        resp = client.get(f"{API_PREFIX}/events/stats", params=params)
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def send_events(source: str, event_type: str, data: dict, count: int = 1) -> str:
    """Send events to Adwize for monitoring.

    Args:
        source: Event source identifier
        event_type: Type of event
        data: Event payload as a dictionary
        count: Number of identical events to send
    """
    batch = {
        "source": source,
        "events": [{"type": event_type, "data": data} for _ in range(count)],
    }

    with _client() as client:
        resp = client.post(f"{API_PREFIX}/events", json=batch)
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def list_rules(active_only: bool = False) -> str:
    """List all monitoring rules.

    Args:
        active_only: Only show active rules
    """
    params = {}
    if active_only:
        params["active_only"] = True

    with _client() as client:
        resp = client.get(f"{API_PREFIX}/rules/", params=params)
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def create_rule(
    name: str,
    rule_type: str,
    config: dict,
    tag: str | None = None,
    category: str | None = None,
) -> str:
    """Create a new monitoring rule.

    Args:
        name: Human-readable rule name
        rule_type: One of THRESHOLD, FIELD_VALIDATION, or VOLUME
        config: Rule configuration (varies by type).
            THRESHOLD: {source, event_type, field: "count", operator: ">", value: 100, window_minutes: 5, severity: "warning"}
            FIELD_VALIDATION: {event_type: "purchase", required_fields: ["user_id", "amount"], severity: "warning"}
            VOLUME: {event_type: "page_view", threshold_percent: -50, current_window_minutes: 60, severity: "critical"}
        tag: Optional tag for grouping
        category: Optional category for grouping
    """
    payload: dict = {
        "name": name,
        "rule_type": rule_type,
        "config": config,
        "is_active": True,
    }
    if tag:
        payload["tag"] = tag
    if category:
        payload["category"] = category

    with _client() as client:
        resp = client.post(f"{API_PREFIX}/rules/", json=payload)
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def toggle_rule(rule_id: str, active: bool) -> str:
    """Enable or disable a monitoring rule.

    Args:
        rule_id: UUID of the rule
        active: True to enable, False to disable
    """
    with _client() as client:
        resp = client.patch(f"{API_PREFIX}/rules/{rule_id}", json={"is_active": active})
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def delete_rule(rule_id: str) -> str:
    """Delete a monitoring rule.

    Args:
        rule_id: UUID of the rule to delete
    """
    with _client() as client:
        resp = client.delete(f"{API_PREFIX}/rules/{rule_id}")
        resp.raise_for_status()
        return f"Rule {rule_id} deleted."


@mcp.tool()
def list_alerts(
    severity: str | None = None,
    resolved: bool | None = None,
    limit: int = 20,
) -> str:
    """List alerts triggered by monitoring rules.

    Args:
        severity: Filter by severity (info, warning, critical)
        resolved: True for resolved, False for unresolved, None for all
        limit: Number of alerts to return
    """
    params: dict = {"limit": limit}
    if severity:
        params["severity"] = severity
    if resolved is not None:
        params["resolved"] = resolved

    with _client() as client:
        resp = client.get(f"{API_PREFIX}/alerts/", params=params)
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def list_grouped_alerts(
    status: str | None = None,
    severity: str | None = None,
) -> str:
    """List alerts grouped by rule, showing occurrence counts and trends.

    Args:
        status: Filter by status (active, acknowledged, resolved)
        severity: Filter by severity (info, warning, critical)
    """
    params: dict = {}
    if status:
        params["status"] = status
    if severity:
        params["severity"] = severity

    with _client() as client:
        resp = client.get(f"{API_PREFIX}/alerts/grouped", params=params)
        resp.raise_for_status()
        return json.dumps(resp.json(), indent=2)


@mcp.tool()
def resolve_alert(alert_id: str, note: str | None = None) -> str:
    """Resolve an alert.

    Args:
        alert_id: UUID of the alert
        note: Optional resolution note
    """
    payload = {}
    if note:
        payload["note"] = note

    with _client() as client:
        resp = client.post(f"{API_PREFIX}/alerts/{alert_id}/resolve", json=payload)
        resp.raise_for_status()
        return f"Alert {alert_id} resolved."


@mcp.tool()
def acknowledge_alert(alert_id: str, note: str | None = None) -> str:
    """Acknowledge an alert.

    Args:
        alert_id: UUID of the alert
        note: Optional acknowledgment note
    """
    payload = {}
    if note:
        payload["note"] = note

    with _client() as client:
        resp = client.post(f"{API_PREFIX}/alerts/{alert_id}/acknowledge", json=payload)
        resp.raise_for_status()
        return f"Alert {alert_id} acknowledged."


@mcp.tool()
def test_webhook(webhook_url: str, webhook_type: str = "webhook") -> str:
    """Send a test notification to verify webhook configuration.

    Args:
        webhook_url: The webhook URL to test
        webhook_type: Type of webhook: 'webhook', 'slack', or 'teams'
    """
    with _client() as client:
        resp = client.post(
            f"{API_PREFIX}/alerts/test-notification",
            json={"webhook_url": webhook_url, "webhook_type": webhook_type},
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("success"):
            return f"Test notification sent successfully to {webhook_url}"
        else:
            return f"Failed to send test notification to {webhook_url}"


@mcp.tool()
def check_status() -> str:
    """Check the health and summary of the Adwize instance."""
    with _client() as client:
        health_resp = client.get(f"{API_BASE}/health")
        health = health_resp.json()

        stats_resp = client.get(f"{API_PREFIX}/events/stats")
        stats = stats_resp.json()

        rules_resp = client.get(f"{API_PREFIX}/rules/", params={"limit": 100})
        rules = rules_resp.json()

    active_rules = sum(1 for r in rules if r.get("is_active"))

    return json.dumps(
        {
            "status": health.get("status"),
            "version": health.get("version"),
            "events_24h": stats.get("total_events_24h", 0),
            "active_rules": active_rules,
            "total_rules": len(rules),
        },
        indent=2,
    )


@mcp.resource("adwize://status")
def resource_status() -> str:
    """Current health and summary of the Adwize instance."""
    try:
        with _client() as client:
            health = client.get(f"{API_BASE}/health").json()
            stats = client.get(f"{API_PREFIX}/events/stats").json()
            rules = client.get(f"{API_PREFIX}/rules/", params={"limit": 100}).json()
            alerts = client.get(
                f"{API_PREFIX}/alerts/", params={"limit": 1, "resolved": False}
            ).json()

        return json.dumps(
            {
                "status": health.get("status"),
                "version": health.get("version"),
                "api_url": API_BASE,
                "events_24h": stats.get("total_events_24h", 0),
                "active_rules": sum(1 for r in rules if r.get("is_active")),
                "total_rules": len(rules),
                "unresolved_alerts": len(alerts),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"status": "unreachable", "error": str(e), "api_url": API_BASE})


@mcp.resource("adwize://rules")
def resource_rules() -> str:
    """All monitoring rules configured in Adwize."""
    try:
        with _client() as client:
            rules = client.get(f"{API_PREFIX}/rules/", params={"limit": 100}).json()
        return json.dumps(rules, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("adwize://alerts")
def resource_alerts() -> str:
    """Recent unresolved alerts from Adwize."""
    try:
        with _client() as client:
            alerts = client.get(
                f"{API_PREFIX}/alerts/", params={"limit": 50, "resolved": False}
            ).json()
        return json.dumps(alerts, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("adwize://config")
def resource_config() -> str:
    """Current Adwize MCP server configuration."""
    return json.dumps(
        {
            "api_url": API_BASE,
            "api_key_configured": bool(os.getenv("ADWIZE_API_KEY")),
            "rule_types": ["THRESHOLD", "FIELD_VALIDATION", "VOLUME"],
            "severity_levels": ["info", "warning", "critical"],
            "endpoints": {
                "events": f"{API_PREFIX}/events",
                "rules": f"{API_PREFIX}/rules/",
                "alerts": f"{API_PREFIX}/alerts/",
                "health": f"{API_BASE}/health",
                "docs": f"{API_BASE}/docs",
            },
        },
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
