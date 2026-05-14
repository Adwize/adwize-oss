import json

import typer
from rich.console import Console
from rich.table import Table

from cli.client import api_url, get_client

app = typer.Typer()
console = Console()

SEVERITY_STYLES = {
    "info": "blue",
    "warning": "yellow",
    "critical": "red bold",
}


@app.command("list")
def list_alerts(
    severity: str | None = typer.Option(None, "--severity", help="Filter by severity"),
    resolved: bool | None = typer.Option(None, "--resolved/--unresolved", help="Filter by status"),
    rule_id: str | None = typer.Option(None, "--rule", help="Filter by rule ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of alerts"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table | json"),
):
    """List alerts."""
    with get_client() as client:
        params: dict = {"limit": limit}
        if severity:
            params["severity"] = severity
        if resolved is not None:
            params["resolved"] = resolved
        if rule_id:
            params["rule_id"] = rule_id

        resp = client.get(api_url("/alerts/"), params=params)
        resp.raise_for_status()
        alerts = resp.json()

    if output == "json":
        console.print_json(json.dumps(alerts))
        return

    table = Table(title="Alerts")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Severity")
    table.add_column("Message", max_width=50)
    table.add_column("Events", justify="right")
    table.add_column("Triggered At")
    table.add_column("Status")

    for a in alerts:
        sev = a["severity"]
        style = SEVERITY_STYLES.get(sev, "")
        sev_display = f"[{style}]{sev.upper()}[/{style}]"

        if a.get("resolved_at"):
            status = "[green]Resolved[/green]"
        elif a.get("acknowledged_at"):
            status = "[yellow]Acked[/yellow]"
        elif a.get("snoozed_until"):
            status = "[dim]Snoozed[/dim]"
        else:
            status = "[red]Active[/red]"

        table.add_row(
            str(a["id"])[:8],
            sev_display,
            a["message"][:50],
            str(a["event_count"]),
            a.get("triggered_at", ""),
            status,
        )

    console.print(table)


@app.command("grouped")
def list_grouped(
    status_filter: str | None = typer.Option(
        None, "--status", help="Filter: active | acknowledged | resolved"
    ),
    severity: str | None = typer.Option(None, "--severity", help="Filter by severity"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table | json"),
):
    """List alerts grouped by rule."""
    with get_client() as client:
        params: dict = {}
        if status_filter:
            params["status"] = status_filter
        if severity:
            params["severity"] = severity

        resp = client.get(api_url("/alerts/grouped"), params=params)
        resp.raise_for_status()
        groups = resp.json()

    if output == "json":
        console.print_json(json.dumps(groups))
        return

    table = Table(title="Grouped Alerts")
    table.add_column("Rule", style="bold", max_width=30)
    table.add_column("Type", style="cyan")
    table.add_column("Severity")
    table.add_column("Occurrences", justify="right")
    table.add_column("Status")
    table.add_column("Last Seen")

    for g in groups:
        sev = g["severity"]
        style = SEVERITY_STYLES.get(sev, "")
        table.add_row(
            g["rule_name"],
            g["rule_type"],
            f"[{style}]{sev.upper()}[/{style}]",
            str(g["occurrence_count"]),
            g["status"].upper(),
            g.get("last_seen", ""),
        )

    console.print(table)


@app.command("resolve")
def resolve_alert(
    alert_id: str = typer.Argument(..., help="Alert ID"),
    note: str | None = typer.Option(None, "--note", "-n", help="Resolution note"),
):
    """Resolve an alert."""
    with get_client() as client:
        payload = {}
        if note:
            payload["note"] = note
        resp = client.post(api_url(f"/alerts/{alert_id}/resolve"), json=payload)
        resp.raise_for_status()

    console.print(f"[green]Alert {alert_id[:8]} resolved[/green]")


@app.command("ack")
def acknowledge_alert(
    alert_id: str = typer.Argument(..., help="Alert ID"),
    note: str | None = typer.Option(None, "--note", "-n", help="Acknowledgment note"),
):
    """Acknowledge an alert."""
    with get_client() as client:
        payload = {}
        if note:
            payload["note"] = note
        resp = client.post(api_url(f"/alerts/{alert_id}/acknowledge"), json=payload)
        resp.raise_for_status()

    console.print(f"[yellow]Alert {alert_id[:8]} acknowledged[/yellow]")


@app.command("snooze")
def snooze_alert(
    alert_id: str = typer.Argument(..., help="Alert ID"),
    minutes: int = typer.Option(60, "--minutes", "-m", help="Snooze duration in minutes"),
):
    """Snooze an alert."""
    with get_client() as client:
        resp = client.post(
            api_url(f"/alerts/{alert_id}/snooze"), json={"duration_minutes": minutes}
        )
        resp.raise_for_status()

    console.print(f"[dim]Alert {alert_id[:8]} snoozed for {minutes} minutes[/dim]")


@app.command("test-webhook")
def test_webhook(
    url: str = typer.Option(..., "--url", help="Webhook URL to test"),
    webhook_type: str = typer.Option(
        "webhook", "--type", "-t", help="Type: slack | teams | webhook"
    ),
):
    """Send a test notification to a webhook."""
    with get_client() as client:
        resp = client.post(
            api_url("/alerts/test-notification"),
            json={"webhook_url": url, "webhook_type": webhook_type},
        )
        resp.raise_for_status()
        result = resp.json()

    if result.get("success"):
        console.print(f"[green]Test notification sent to {url}[/green]")
    else:
        console.print("[red]Failed to send test notification[/red]")
