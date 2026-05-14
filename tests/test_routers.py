"""Integration tests for API routers using ASGI transport (no real DB)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def app_no_auth(mock_db):
    from api.database import get_db
    from api.main import app

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    with patch("api.auth.get_settings") as mock_settings:
        mock_settings.return_value.api_key = None
        yield app

    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_no_auth):
    transport = ASGITransport(app=app_no_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthRouter:
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data

    async def test_health_returns_app_name(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert data["app"] == "Adwize"


class TestEventsRouter:
    async def test_ingest_events_success(self, client, mock_db):
        with patch("api.routers.events.bulk_insert_events", new_callable=AsyncMock):
            resp = await client.post(
                "/api/v1/events",
                json={
                    "source": "web",
                    "events": [
                        {
                            "type": "page_view",
                            "data": {"url": "/home"},
                        }
                    ],
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["events_received"] == 1

    async def test_ingest_events_empty_batch_rejected(self, client):
        resp = await client.post(
            "/api/v1/events",
            json={"source": "web", "events": []},
        )
        assert resp.status_code == 422

    async def test_ingest_events_missing_source(self, client):
        resp = await client.post(
            "/api/v1/events",
            json={"events": [{"type": "click", "data": {}}]},
        )
        assert resp.status_code == 422

    async def test_list_events(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.get("/api/v1/events/")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert data["events"] == []

    async def test_event_stats(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.get("/api/v1/events/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events_24h"] == 0


class TestRulesRouter:
    async def test_create_rule_success(self, client, mock_db):
        from api.models.rule import Rule, RuleType

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        fake_rule = Rule(
            id=uuid.uuid4(),
            name="Test threshold",
            rule_type=RuleType.THRESHOLD,
            is_active=True,
            config={
                "event_type": "error",
                "field": "count",
                "operator": ">",
                "value": 100,
                "window_minutes": 10,
                "severity": "warning",
            },
            tag=None,
            category=None,
            created_at=now,
            updated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            for attr in (
                "id",
                "name",
                "rule_type",
                "is_active",
                "config",
                "tag",
                "category",
                "created_at",
                "updated_at",
            ):
                setattr(obj, attr, getattr(fake_rule, attr))

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        resp = await client.post(
            "/api/v1/rules/",
            json={
                "name": "Test threshold",
                "rule_type": "THRESHOLD",
                "config": {
                    "event_type": "error",
                    "field": "count",
                    "operator": ">",
                    "value": 100,
                    "window_minutes": 10,
                    "severity": "warning",
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test threshold"
        assert data["rule_type"] == "THRESHOLD"
        assert data["is_active"] is True

    async def test_create_rule_invalid_config(self, client, mock_db):
        resp = await client.post(
            "/api/v1/rules/",
            json={
                "name": "Bad rule",
                "rule_type": "THRESHOLD",
                "config": {"bad_field": "no"},
            },
        )
        assert resp.status_code == 422

    async def test_create_rule_empty_name(self, client, mock_db):
        resp = await client.post(
            "/api/v1/rules/",
            json={
                "name": "",
                "rule_type": "THRESHOLD",
                "config": {
                    "event_type": "error",
                    "field": "count",
                    "operator": ">",
                    "value": 100,
                    "window_minutes": 10,
                    "severity": "warning",
                },
            },
        )
        assert resp.status_code == 422

    async def test_list_rules(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.get("/api/v1/rules/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_rule_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.get(f"/api/v1/rules/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_rule_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.delete(f"/api/v1/rules/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestAlertsRouter:
    async def test_list_alerts(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.get("/api/v1/alerts/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_alert_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.get(f"/api/v1/alerts/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_resolve_alert_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.post(
            f"/api/v1/alerts/{uuid.uuid4()}/resolve",
            json={},
        )
        assert resp.status_code == 404

    async def test_snooze_alert_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.post(
            f"/api/v1/alerts/{uuid.uuid4()}/snooze",
            json={"duration_minutes": 30},
        )
        assert resp.status_code == 404

    async def test_error_details_not_leaked(self, client, mock_db):
        """Verify that internal error details are not exposed in 500 responses."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await client.delete(f"/api/v1/alerts/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert "traceback" not in resp.text.lower()
        assert "sqlalchemy" not in resp.text.lower()
