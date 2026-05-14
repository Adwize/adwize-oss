import json

import typer
from rich.console import Console
from rich.table import Table

from cli.client import api_url, get_client

app = typer.Typer()
console = Console()


@app.command("list")
def list_rules(
    active_only: bool = typer.Option(False, "--active", help="Show active rules only"),
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table | json"),
):
    """List all monitoring rules."""
    with get_client() as client:
        params = {}
        if active_only:
            params["active_only"] = True
        if tag:
            params["tag"] = tag
        resp = client.get(api_url("/rules/"), params=params)
        resp.raise_for_status()
        rules = resp.json()

    if output == "json":
        console.print_json(json.dumps(rules))
        return

    table = Table(title="Rules")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Name", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Active", justify="center")
    table.add_column("Tag")

    for r in rules:
        active = "[green]Yes[/green]" if r["is_active"] else "[red]No[/red]"
        table.add_row(
            str(r["id"])[:8],
            r["name"],
            r["rule_type"],
            active,
            r.get("tag") or "",
        )

    console.print(table)


@app.command("get")
def get_rule(rule_id: str = typer.Argument(..., help="Rule ID")):
    """Get details for a specific rule."""
    with get_client() as client:
        resp = client.get(api_url(f"/rules/{rule_id}"))
        resp.raise_for_status()
        rule = resp.json()

    console.print_json(json.dumps(rule, indent=2))


@app.command("create")
def create_rule(
    name: str = typer.Option(..., "--name", "-n", help="Rule name"),
    rule_type: str = typer.Option(
        ..., "--type", "-t", help="Rule type: THRESHOLD | FIELD_VALIDATION | VOLUME"
    ),
    config_json: str = typer.Option(..., "--config", "-c", help="Rule config as JSON string"),
    tag: str | None = typer.Option(None, "--tag", help="Optional tag"),
    category: str | None = typer.Option(None, "--category", help="Optional category"),
):
    """Create a new monitoring rule."""
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON config[/red]")
        raise typer.Exit(1)

    payload = {
        "name": name,
        "rule_type": rule_type,
        "config": config,
        "is_active": True,
    }
    if tag:
        payload["tag"] = tag
    if category:
        payload["category"] = category

    with get_client() as client:
        resp = client.post(api_url("/rules/"), json=payload)
        if resp.status_code == 422:
            console.print(f"[red]Validation error:[/red] {resp.json()['detail']}")
            raise typer.Exit(1)
        resp.raise_for_status()
        rule = resp.json()

    console.print(f"[green]Rule created:[/green] {rule['id']}")
    console.print(f"  Name: {rule['name']}")
    console.print(f"  Type: {rule['rule_type']}")


@app.command("toggle")
def toggle_rule(
    rule_id: str = typer.Argument(..., help="Rule ID"),
    active: bool = typer.Option(..., "--active/--inactive", help="Enable or disable the rule"),
):
    """Enable or disable a rule."""
    with get_client() as client:
        resp = client.patch(api_url(f"/rules/{rule_id}"), json={"is_active": active})
        resp.raise_for_status()
        rule = resp.json()

    status = "[green]enabled[/green]" if rule["is_active"] else "[red]disabled[/red]"
    console.print(f"Rule {rule['name']} is now {status}")


@app.command("delete")
def delete_rule(
    rule_id: str = typer.Argument(..., help="Rule ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a rule."""
    if not confirm:
        typer.confirm(f"Delete rule {rule_id}?", abort=True)

    with get_client() as client:
        resp = client.delete(api_url(f"/rules/{rule_id}"))
        resp.raise_for_status()

    console.print(f"[green]Rule {rule_id} deleted[/green]")
