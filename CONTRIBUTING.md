# Contributing to Adwize

Thanks for your interest in contributing to Adwize! This guide will help you get started.

## Development Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/tagsavvy/adwize-oss.git
   cd adwize-oss
   ```

2. **Install dependencies** (requires [uv](https://docs.astral.sh/uv/)):
   ```bash
   uv sync --extra dev
   ```

3. **Start the backend** (requires Docker):
   ```bash
   cp .env.example .env   # edit DB_PASSWORD at minimum
   docker compose up -d
   ```

4. **Run tests:**
   ```bash
   uv run pytest tests/ -v
   ```

5. **Run linting:**
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   ```

## Project Structure

| Directory      | Description                              |
|----------------|------------------------------------------|
| `api/`         | FastAPI backend (models, schemas, routes) |
| `worker/`      | Background rule evaluation worker        |
| `cli/`         | Typer CLI application                    |
| `mcp_server/`  | MCP server for AI assistants             |
| `migrations/`  | Alembic database migrations              |
| `tests/`       | Test suite                               |

## Making Changes

1. Create a branch from `main`.
2. Make your changes with clear, focused commits.
3. Ensure all tests pass and linting is clean.
4. Open a pull request against `main`.

## Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- Line length limit is 100 characters.
- Target Python version is 3.12+.
- Use type annotations throughout.

## Running the Full Stack Locally

```bash
# Backend (Postgres + API + Worker)
docker compose up -d

# CLI (on host)
uv run adwize status

# MCP dev inspector
ADWIZE_API_URL=http://localhost:8000 uv run mcp dev mcp_server/server.py
```

## Reporting Issues

Please use GitHub Issues. Include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, Docker version)

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
