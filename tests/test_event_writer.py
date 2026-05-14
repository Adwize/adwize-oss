import uuid
from datetime import datetime, timezone

from api.services.event_writer import normalize_event, normalize_timestamp


class TestNormalizeTimestamp:
    def test_none_returns_utc_now(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        result = normalize_timestamp(None)
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        assert result.tzinfo is None
        assert before <= result <= after

    def test_naive_datetime_passthrough(self):
        dt = datetime(2025, 6, 15, 12, 0, 0)
        result = normalize_timestamp(dt)

        assert result == dt
        assert result.tzinfo is None

    def test_aware_datetime_stripped(self):
        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = normalize_timestamp(dt)

        assert result == datetime(2025, 6, 15, 12, 0, 0)
        assert result.tzinfo is None

    def test_epoch_milliseconds_int(self):
        ts_ms = 1718452800000  # 2024-06-15T12:00:00Z
        result = normalize_timestamp(ts_ms)

        assert result == datetime(2024, 6, 15, 12, 0, 0)
        assert result.tzinfo is None

    def test_epoch_milliseconds_float(self):
        ts_ms = 1718452800000.0
        result = normalize_timestamp(ts_ms)

        assert result == datetime(2024, 6, 15, 12, 0, 0)
        assert result.tzinfo is None

    def test_iso_string(self):
        result = normalize_timestamp("2025-06-15T12:00:00+00:00")

        assert result == datetime(2025, 6, 15, 12, 0, 0)
        assert result.tzinfo is None

    def test_iso_string_with_z(self):
        result = normalize_timestamp("2025-06-15T12:00:00Z")

        assert result == datetime(2025, 6, 15, 12, 0, 0)
        assert result.tzinfo is None

    def test_iso_string_with_offset(self):
        result = normalize_timestamp("2025-06-15T14:00:00+02:00")

        assert result == datetime(2025, 6, 15, 12, 0, 0)
        assert result.tzinfo is None

    def test_invalid_string_returns_now(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        result = normalize_timestamp("not-a-date")
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        assert result.tzinfo is None
        assert before <= result <= after

    def test_zero_epoch(self):
        result = normalize_timestamp(0)
        assert result == datetime(1970, 1, 1, 0, 0, 0)


class TestNormalizeEvent:
    def test_returns_dict_with_all_fields(self):
        row = normalize_event(
            source="web",
            event_type="purchase",
            event_data={"value": 99.99},
        )

        assert isinstance(row, dict)
        assert set(row.keys()) == {"id", "source", "event_type", "event_data", "received_at"}
        assert isinstance(row["id"], uuid.UUID)
        assert row["source"] == "web"
        assert row["event_type"] == "purchase"
        assert row["event_data"] == {"value": 99.99}
        assert isinstance(row["received_at"], datetime)
        assert row["received_at"].tzinfo is None

    def test_generates_unique_ids(self):
        rows = [
            normalize_event(
                source="test",
                event_type="click",
                event_data={"i": i},
            )
            for i in range(100)
        ]

        ids = {r["id"] for r in rows}
        assert len(ids) == 100

    def test_passes_timestamp_to_normalize(self):
        row = normalize_event(
            source="sdk",
            event_type="view",
            event_data={},
            timestamp="2025-06-15T12:00:00Z",
        )

        assert row["received_at"] == datetime(2025, 6, 15, 12, 0, 0)

    def test_non_dict_event_data_wrapped(self):
        row = normalize_event(
            source="webhook",
            event_type="raw",
            event_data="some string payload",
        )

        assert row["event_data"] == {"raw": "some string payload"}

    def test_dict_event_data_preserved(self):
        data = {"nested": {"key": [1, 2, 3]}, "flag": True}
        row = normalize_event(
            source="amplitude",
            event_type="track",
            event_data=data,
        )

        assert row["event_data"] == data

    def test_none_timestamp_uses_now(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        row = normalize_event(
            source="test",
            event_type="ping",
            event_data={},
            timestamp=None,
        )
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        assert before <= row["received_at"] <= after
