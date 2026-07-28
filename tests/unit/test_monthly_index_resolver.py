from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.query.index_resolver import IndexResolutionError, MonthlyIndexResolver
from app.semantic.compiler import SemanticCompiler, SemanticSourcePaths

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolver() -> MonthlyIndexResolver:
    model = SemanticCompiler(SemanticSourcePaths.from_project_root(PROJECT_ROOT)).compile().model
    return MonthlyIndexResolver(model.policy)


def test_single_month_does_not_include_exclusive_next_month() -> None:
    resolution = _resolver().resolve(
        datetime.fromisoformat("2026-07-01T00:00:00+08:00"),
        datetime.fromisoformat("2026-08-01T00:00:00+08:00"),
    )

    assert resolution.indices == ["tbl_os_sub_message_2026_07"]


def test_cross_month_range_resolves_every_intersecting_partition() -> None:
    resolution = _resolver().resolve(
        datetime.fromisoformat("2026-06-20T00:00:00+08:00"),
        datetime.fromisoformat("2026-08-05T00:00:00+08:00"),
    )

    assert resolution.indices == [
        "tbl_os_sub_message_2026_06",
        "tbl_os_sub_message_2026_07",
        "tbl_os_sub_message_2026_08",
    ]


def test_missing_inventory_is_reported_not_silently_dropped() -> None:
    resolution = _resolver().resolve(
        datetime.fromisoformat("2026-06-01T00:00:00+08:00"),
        datetime.fromisoformat("2026-08-01T00:00:00+08:00"),
        available_indices={"tbl_os_sub_message_2026_07"},
    )

    assert resolution.missing_indices == ["tbl_os_sub_message_2026_06"]


def test_range_over_policy_is_rejected() -> None:
    with pytest.raises(IndexResolutionError, match="time range exceeds"):
        _resolver().resolve(
            datetime.fromisoformat("2025-01-01T00:00:00+08:00"),
            datetime.fromisoformat("2026-07-01T00:00:00+08:00"),
        )
