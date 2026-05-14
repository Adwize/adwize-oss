import os
import shutil
import subprocess
import time

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from cli import config

console = Console()

MCP_SNIPPET = """{
  "mcpServers": {
    "adwize": {
      "command": "uv",
      "args": ["run", "python", "mcp_server/server.py"],
      "cwd": "%s",
      "env": {
        "ADWIZE_API_URL": "%s"
      }
    }
  }
}"""


def _wait_for_health(api_url: str, timeout: int = 30) -> bool:
    """Poll /health until it responds or timeout."""
    url = f"{api_url}/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(2)
    return False


def run_setup():
    """Interactive setup wizard for Adwize."""
    console.print(
        Panel.fit(
            "[bold]Adwize Setup Wizard[/bold]\nThis will configure your local Adwize instance.",
            border_style="blue",
        )
    )

    # --- Docker check ---
    if not shutil.which("docker"):
        console.print("[red]Docker is not installed or not in PATH.[/red]")
        console.print("Please install Docker Desktop: https://docs.docker.com/get-docker/")
        raise typer.Exit(1)

    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[red]Docker daemon is not running.[/red]")
        console.print("Please start Docker Desktop and try again.")
        raise typer.Exit(1)

    console.print("[green]Docker is running.[/green]\n")

    # --- Gather configuration ---
    existing = config.load()

    api_url = Prompt.ask(
        "API URL",
        default=existing.get("api_url", "http://localhost:8000"),
    )

    db_password = Prompt.ask("Database password", default="changeme")

    api_key = Prompt.ask(
        "API key [dim](leave empty for no auth)[/dim]",
        default=existing.get("api_key") or "",
    )

    webhook_url = Prompt.ask(
        "Default webhook URL [dim](leave empty to skip)[/dim]",
        default=existing.get("webhook_url") or "",
    )

    # --- Write .env file ---
    project_dir = os.getcwd()
    env_path = os.path.join(project_dir, ".env")

    env_content = f"DB_PASSWORD={db_password}\nDB_NAME=adwize\nDB_USER=postgres\n"
    if api_key:
        env_content += f"API_KEY={api_key}\n"
    if webhook_url:
        env_content += f"WEBHOOK_URL={webhook_url}\n"

    should_write_env = True
    if os.path.exists(env_path):
        if not Confirm.ask("\n.env file already exists. Overwrite?", default=False):
            console.print("[yellow]Keeping existing .env file.[/yellow]")
            should_write_env = False

    if should_write_env:
        with open(env_path, "w") as f:
            f.write(env_content)
        console.print("[green].env file saved.[/green]")

    # --- Save config to ~/.adwize/config.json ---
    cfg = {
        "api_url": api_url,
        "api_key": api_key or None,
        "webhook_url": webhook_url or None,
        "project_dir": project_dir,
    }
    config_path = config.save(cfg)
    console.print(f"[green]Config saved to {config_path}[/green]")

    # --- Start Docker Compose ---
    console.print()
    if Confirm.ask("Start Adwize with Docker Compose?", default=True):
        console.print("\n[bold]Starting services...[/bold]\n")

        compose_file = os.path.join(project_dir, "docker-compose.yml")
        if not os.path.exists(compose_file):
            console.print(f"[red]docker-compose.yml not found in {project_dir}[/red]")
            console.print("Make sure you're in the adwize-oss directory.")
            raise typer.Exit(1)

        subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=project_dir)

        # --- Wait for health ---
        console.print("\n[dim]Waiting for API to be ready...[/dim]")
        if _wait_for_health(api_url):
            console.print("[green]API is healthy.[/green]\n")
        else:
            console.print(
                "[yellow]API did not respond within 30s. It may still be starting.[/yellow]"
            )
            console.print("[dim]Check with: adwize status[/dim]\n")
    else:
        console.print(
            "\n[dim]Run 'docker compose up -d --build' when you're ready to start.[/dim]\n"
        )

    # --- Test webhook ---
    if webhook_url:
        if Confirm.ask("Send a test webhook notification?", default=True):
            try:
                resp = httpx.post(
                    f"{api_url}/api/v1/alerts/test-notification",
                    json={"webhook_url": webhook_url, "webhook_type": "webhook"},
                    headers={"X-Api-Key": api_key} if api_key else {},
                    timeout=15,
                )
                if resp.status_code == 200 and resp.json().get("success"):
                    console.print("[green]Test webhook sent — check your channel.[/green]\n")
                else:
                    console.print(
                        "[yellow]Webhook test returned non-success. Check the URL.[/yellow]\n"
                    )
            except Exception as e:
                console.print(f"[yellow]Could not send test webhook: {e}[/yellow]\n")

    # --- Print MCP snippet ---
    console.print(
        Panel(
            "[bold]MCP Server Configuration[/bold]\n\n"
            "Add this to your AI assistant's MCP config\n"
            "(Cursor: .cursor/mcp.json, Claude Desktop: claude_desktop_config.json):",
            border_style="dim",
        )
    )
    snippet = MCP_SNIPPET % (project_dir, api_url)
    console.print(Syntax(snippet, "json", theme="monokai", padding=1))

    # --- Summary ---
    console.print(
        Panel.fit(
            "[bold green]Setup complete![/bold green]\n\n"
            f"  API:    {api_url}\n"
            f"  Docs:   {api_url}/docs\n"
            f"  Config: {config_path}\n" + (f"  API Key: {api_key}\n" if api_key else "") + "\n"
            "  [dim]adwize status          — check health[/dim]\n"
            "  [dim]adwize events list     — view events[/dim]\n"
            "  [dim]adwize rules list      — view rules[/dim]\n"
            "  [dim]adwize alerts list     — view alerts[/dim]",
            border_style="green",
        )
    )
