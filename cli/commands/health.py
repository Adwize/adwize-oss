import httpx
import typer
from rich.console import Console

from cli.client import get_base_url, get_client

console = Console()


def check_health():
    """Check if the Adwize API is healthy."""
    base = get_base_url()

    try:
        with get_client() as client:
            resp = client.get(f"{base}/health")
            data = resp.json()
    except httpx.ConnectError:
        console.print(f"[red]Cannot connect to {base}[/red]")
        console.print("[dim]Is Adwize running? Try: adwize up[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if data.get("status") == "healthy":
        console.print(f"[green]Adwize {data.get('version', '?')} is healthy[/green] at {base}")
    else:
        console.print(f"[red]Adwize is unhealthy[/red] at {base}")
        raise typer.Exit(1)
