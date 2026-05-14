import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.client import api_url, get_base_url, get_client

console = Console()


def show_status():
    """Check Adwize API health and show summary."""
    base = get_base_url()

    try:
        with get_client() as client:
            health_resp = client.get(f"{base}/health")
            health = health_resp.json()
    except httpx.ConnectError:
        console.print(
            Panel(
                f"[red bold]Cannot connect to Adwize API[/red bold]\n\n"
                f"  URL: {base}\n\n"
                f"  Make sure the API is running:\n"
                f"  [dim]docker compose up -d[/dim]",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    status_emoji = (
        "[green]healthy[/green]" if health.get("status") == "healthy" else "[red]unhealthy[/red]"
    )

    console.print(f"\n  Adwize {health.get('version', '?')} — {status_emoji}")
    console.print(f"  API: {base}\n")

    try:
        with get_client() as client:
            stats_resp = client.get(api_url("/events/stats"))
            stats = stats_resp.json()

            rules_resp = client.get(api_url("/rules/"), params={"limit": 100})
            rules = rules_resp.json()

            alerts_resp = client.get(api_url("/alerts/"), params={"limit": 1, "resolved": False})
            alerts = alerts_resp.json()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Events (24h)", str(stats.get("total_events_24h", 0)))
        table.add_row("Active rules", str(sum(1 for r in rules if r.get("is_active"))))
        table.add_row("Total rules", str(len(rules)))
        table.add_row("Unresolved alerts", str(len(alerts)))

        console.print(table)
        console.print()

    except Exception:
        console.print("[dim]  Could not fetch summary stats.[/dim]\n")
