"""MCP smoke DSL is deterministic, bounded, and injection resistant."""

import pytest

from app.cli import _build_smoke_queries


def test_builds_fixed_read_only_smoke_sequence() -> None:
    queries = _build_smoke_queries(
        time_field="event_time",
        channel_field="channel",
        status_field="status",
        from_inclusive="2026-05-01T00:00:00+08:00",
        to_exclusive="2026-08-01T00:00:00+08:00",
        timezone="Asia/Hong_Kong",
    )

    assert tuple(queries) == (
        "count_narrow_range",
        "channel_aggregation",
        "channel_status_aggregation",
        "multi_month_aggregation",
    )
    assert all(query["size"] == 0 for query in queries.values())
    assert all(query["timeout"] == "10s" for query in queries.values())
    month = queries["multi_month_aggregation"]["aggs"]["by_month"]["date_histogram"]
    assert month["calendar_interval"] == "month"
    assert month["time_zone"] == "Asia/Hong_Kong"


def test_rejects_field_injection_and_naive_time_range() -> None:
    with pytest.raises(ValueError, match="safe physical paths"):
        _build_smoke_queries(
            time_field="event_time; DELETE /index",
            channel_field="channel",
            status_field="status",
            from_inclusive="2026-07-01T00:00:00+08:00",
            to_exclusive="2026-08-01T00:00:00+08:00",
            timezone="Asia/Hong_Kong",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        _build_smoke_queries(
            time_field="event_time",
            channel_field="channel",
            status_field="status",
            from_inclusive="2026-07-01T00:00:00",
            to_exclusive="2026-08-01T00:00:00",
            timezone="Asia/Hong_Kong",
        )
