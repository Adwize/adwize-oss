import subprocess
import sys

import typer
from rich.console import Console

from cli import config

console = Console()


def _get_project_dir() -> str:
    project_dir = config.get("project_dir")
    if not project_dir:
        console.print("[yellow]Project directory not set. Run 'adwize setup' first,[/yellow]")
        console.print("[yellow]or run this command from the adwize-oss directory.[/yellow]")
        raise typer.Exit(1)
    return project_dir


def compose_up():
    """Start Adwize services (docker compose up -d)."""
    project_dir = _get_project_dir()
    console.print("[bold]Starting Adwize...[/bold]\n")
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=project_dir,
    )
    if result.returncode == 0:
        console.print("\n[green]Adwize is running at http://localhost:8000[/green]")
    sys.exit(result.returncode)


def compose_down():
    """Stop Adwize services (docker compose down)."""
    project_dir = _get_project_dir()
    console.print("[bold]Stopping Adwize...[/bold]\n")
    result = subprocess.run(
        ["docker", "compose", "down"],
        cwd=project_dir,
    )
    if result.returncode == 0:
        console.print("\n[green]Adwize stopped.[/green]")
    sys.exit(result.returncode)


def compose_logs(
    follow: bool = typer.Option(True, "--follow/--no-follow", "-f", help="Follow log output"),
    service: str | None = typer.Option(
        None, "--service", "-s", help="Service name: api | worker | postgres"
    ),
):
    """View Adwize service logs."""
    project_dir = _get_project_dir()
    cmd = ["docker", "compose", "logs"]
    if follow:
        cmd.append("-f")
    if service:
        cmd.append(service)

    try:
        subprocess.run(cmd, cwd=project_dir)
    except KeyboardInterrupt:
        pass
