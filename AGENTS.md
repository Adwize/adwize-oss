# Adwize — AI Agent Reference

Use this reference when asked to monitor events, create rules, inspect alerts, or interact with the Adwize event monitoring platform.

## What is Adwize?

Adwize is an open-source event monitoring tool. It ingests analytics events, evaluates them against deterministic rules (threshold, field validation, volume), and dispatches webhook alerts when violations occur.

## Architecture

- **API**: FastAPI server at `http://localhost:8000` (or configured `ADWIZE_API_URL`)
- **Worker**: Background rule evaluator running every 5 minutes
- **Database**: PostgreSQL with events, rules, alerts, notification_logs tables
- **CLI**: `adwize` command for managing everything from the terminal
- **MCP Server**: AI-native interface at `mcp_server/server.py`

## Quick Reference

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/events` | Ingest events |
| GET | `/api/v1/events/` | List events |
| GET | `/api/v1/events/stats` | Event stats (24h) |
| GET | `/api/v1/events/stream` | Live SSE stream |
| POST | `/api/v1/rules/` | Create rule |
| GET | `/api/v1/rules/` | List rules |
| PATCH | `/api/v1/rules/{id}` | Update rule |
| DELETE | `/api/v1/rules/{id}` | Delete rule |
| GET | `/api/v1/alerts/` | List alerts |
| GET | `/api/v1/alerts/grouped` | Grouped alerts |
| POST | `/api/v1/alerts/{id}/resolve` | Resolve alert |
| POST | `/api/v1/alerts/{id}/acknowledge` | Ack alert |
| POST | `/api/v1/alerts/{id}/snooze` | Snooze alert |

### CLI Commands

```bash
adwize setup                    # Interactive setup wizard
adwize status                   # Health check + summary stats
adwize health                   # Quick health check
adwize up                       # docker compose up -d --build
adwize down                     # docker compose down
adwize logs [-s api]            # docker compose logs -f
adwize mcp                      # Start MCP server (stdio mode)

adwize events list              # List recent events
adwize events send -s web -t page_view -d '{"url":"/home"}'
adwize events tail              # Live tail (SSE stream)
adwize events stats             # Event stats (24h)

adwize rules list               # List rules
adwize rules get <id>           # Rule details
adwize rules create -n "High traffic" -t THRESHOLD -c '{"field":"count","operator":">","value":100,"window_minutes":5}'
adwize rules toggle <id> --active/--inactive
adwize rules delete <id>

adwize alerts list              # List alerts
adwize alerts grouped           # Grouped view by rule
adwize alerts resolve <id>      # Resolve alert
adwize alerts ack <id>          # Acknowledge alert
adwize alerts snooze <id> -m 60 # Snooze for 60 minutes
adwize alerts test-webhook --url https://hooks.slack.com/...
```

### Rule Types

**THRESHOLD** — Alert when event count crosses a threshold in a time window:
```json
{
  "event_type": "error",
  "field": "count",
  "operator": ">",
  "value": 50,
  "window_minutes": 10,
  "severity": "warning"
}
```

**FIELD_VALIDATION** — Alert when events have missing/invalid fields:
```json
{
  "event_type": "purchase",
  "required_fields": ["user_id", "amount", "currency"],
  "allowed_values": {"currency": ["USD", "EUR", "GBP"]},
  "severity": "critical"
}
```

**VOLUME** — Alert when event volume changes significantly vs baseline:
```json
{
  "event_type": "page_view",
  "threshold_percent": -50,
  "current_window_minutes": 60,
  "comparison_window_hours": 24,
  "severity": "critical"
}
```

### Authentication

If `API_KEY` is set in `.env`, include `X-Api-Key: <key>` header. If unset, no auth required.

### Event Ingestion Format

```json
{
  "source": "web",
  "events": [
    {
      "type": "page_view",
      "data": {"url": "/pricing", "user_id": "u123"},
      "timestamp": "2026-01-01T00:00:00Z"
    }
  ]
}
```

## MCP Server

The MCP server exposes the same functionality as the CLI as MCP tools. It works with any MCP-compatible client (Cursor, Claude Desktop, Windsurf, Cline, etc.).

Start it via the CLI: `adwize mcp`

### Configuration

Add to your AI assistant's MCP config (Cursor: `.cursor/mcp.json`, Claude Desktop: `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "adwize": {
      "command": "adwize",
      "args": ["mcp"]
    }
  }
}
```

Or if `adwize` is not on PATH:

```json
{
  "mcpServers": {
    "adwize": {
      "command": "uv",
      "args": ["run", "python", "mcp_server/server.py"],
      "cwd": "/path/to/adwize-oss",
      "env": {
        "ADWIZE_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `list_events` | List recent events with optional filters |
| `send_events` | Send events for monitoring |
| `get_event_stats` | Event statistics (last 24h) |
| `list_rules` | List monitoring rules |
| `create_rule` | Create a new rule |
| `toggle_rule` | Enable/disable a rule |
| `delete_rule` | Delete a rule |
| `list_alerts` | List triggered alerts |
| `list_grouped_alerts` | Alerts grouped by rule |
| `resolve_alert` | Resolve an alert |
| `acknowledge_alert` | Acknowledge an alert |
| `test_webhook` | Send a test notification |
| `check_status` | Health and summary |

## File Locations

- `api/` — FastAPI backend (models, schemas, routers, services)
- `worker/` — Background rule monitoring worker
- `cli/` — Typer CLI application
- `mcp_server/` — MCP server for AI assistants
- `migrations/` — Alembic database migrations
- `docker-compose.yml` — Local orchestration
- `.env.example` — Environment variable template
