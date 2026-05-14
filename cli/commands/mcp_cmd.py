import os
import subprocess
import sys

import typer
from rich.console import Console

from cli import config

console = Console()


def start_mcp():
    """Start the Adwize MCP server (stdio mode for AI assistants)."""
    project_dir = config.get("project_dir") or os.getcwd()
    server_path = os.path.join(project_dir, "mcp_server", "server.py")

    if not os.path.exists(server_path):
        console.print(f"[red]MCP server not found at {server_path}[/red]")
        console.print(
            "[dim]Make sure you're in the adwize-oss directory or run 'adwize setup' first.[/dim]"
        )
        raise typer.Exit(1)

    env = os.environ.copy()
    api_url = config.get("api_url", "http://localhost:8000")
    env["ADWIZE_API_URL"] = api_url

    api_key = config.get("api_key")
    if api_key:
        env["ADWIZE_API_KEY"] = api_key

    try:
        subprocess.run(
            [sys.executable, server_path],
            cwd=project_dir,
            env=env,
        )
    except KeyboardInterrupt:
        pass
