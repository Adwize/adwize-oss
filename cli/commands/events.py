import json
import sys

import typer
from rich.console import Console
from rich.table import Table

from cli.client import api_url, get_client

app = typer.Typer()
console = Console()


@app.command("list")
def list_events(
    source: str | None = typer.Option(None, "--source", "-s", help="Filter by source"),
    event_type: str | None = typer.Option(None, "--type", "-t", help="Filter by event type"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of events"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table | json"),
):
    """List recent events."""
    with get_client() as client:
        params = {"limit": limit}
        if source:
            params["source"] = source
        if event_type:
            params["event_type"] = event_type

        resp = client.get(api_url("/events/"), params=params)
        resp.raise_for_status()
        data = resp.json()

    if output == "json":
        console.print_json(json.dumps(data))
        return

    table = Table(title="Events")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Source", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Received At")

    for e in data.get("events", []):
        table.add_row(
            str(e["id"])[:8],
            e["source"],
            e["event_type"],
            e.get("received_at", ""),
        )

    console.print(table)
    console.print(f"[dim]Showing {len(data.get('events', []))} events[/dim]")


@app.command("stats")
def event_stats(
    source: str | None = typer.Option(None, "--source", "-s", help="Filter by source"),
):
    """Show event statistics (last 24h)."""
    with get_client() as client:
        params = {}
        if source:
            params["source"] = source
        resp = client.get(api_url("/events/stats"), params=params)
        resp.raise_for_status()
        data = resp.json()

    console.print(f"\n[bold]Events (24h): {data['total_events_24h']}[/bold]\n")

    if data.get("by_event_type"):
        table = Table(title="By Event Type")
        table.add_column("Event Type", style="green")
        table.add_column("Count", justify="right")
        for item in data["by_event_type"]:
            table.add_row(item["event_type"], str(item["count"]))
        console.print(table)

    if data.get("by_source"):
        table = Table(title="By Source")
        table.add_column("Source", style="cyan")
        table.add_column("Count", justify="right")
        for item in data["by_source"]:
            table.add_row(item["source"], str(item["count"]))
        console.print(table)


@app.command("send")
def send_events(
    source: str = typer.Option(..., "--source", "-s", help="Event source"),
    event_type: str = typer.Option(..., "--type", "-t", help="Event type"),
    data: str = typer.Option("{}", "--data", "-d", help="JSON payload"),
    count: int = typer.Option(1, "--count", "-c", help="Number of events to send"),
):
    """Send events to the API."""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON data[/red]")
        raise typer.Exit(1)

    batch = {
        "source": source,
        "events": [{"type": event_type, "data": payload} for _ in range(count)],
    }

    with get_client() as client:
        resp = client.post(api_url("/events"), json=batch)
        resp.raise_for_status()
        result = resp.json()

    console.print(f"[green]Sent {result['events_received']} events[/green]")


@app.command("tail")
def tail_events(
    source: str | None = typer.Option(None, "--source", "-s", help="Filter by source"),
    event_type: str | None = typer.Option(None, "--type", "-t", help="Filter by event type"),
):
    """Live tail of incoming events (SSE stream)."""
    import httpx

    from cli.client import get_base_url, get_headers

    params = {}
    if source:
        params["source"] = source
    if event_type:
        params["event_type"] = event_type

    url = f"{get_base_url()}/api/v1/events/stream"
    console.print(f"[dim]Streaming events from {url}... (Ctrl+C to stop)[/dim]\n")

    try:
        with httpx.stream("GET", url, headers=get_headers(), params=params, timeout=None) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        console.print(
                            f"[cyan]{event['source']}[/cyan] "
                            f"[green]{event['event_type']}[/green] "
                            f"[dim]{event.get('received_at', '')}[/dim]"
                        )
                    except json.JSONDecodeError:
                        pass
    except KeyboardInterrupt:
        console.print("\n[dim]Stream stopped.[/dim]")
        sys.exit(0)
