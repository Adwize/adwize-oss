import typer

from cli.commands import alerts, docker, events, health, mcp_cmd, rules, setup, status

app = typer.Typer(
    name="adwize",
    help="Adwize - Open-source event monitoring with deterministic rules and webhook alerts.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(events.app, name="events", help="Manage and inspect events")
app.add_typer(rules.app, name="rules", help="Manage monitoring rules")
app.add_typer(alerts.app, name="alerts", help="Manage and inspect alerts")

app.command("setup")(setup.run_setup)
app.command("status")(status.show_status)
app.command("health")(health.check_health)
app.command("up")(docker.compose_up)
app.command("down")(docker.compose_down)
app.command("logs")(docker.compose_logs)
app.command("mcp")(mcp_cmd.start_mcp)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Adwize - Fix analytics data before it breaks decisions."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
