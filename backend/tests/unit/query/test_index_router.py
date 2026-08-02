"""Monthly routing honors HK half-open ranges, policy, and mapping availability."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.contracts.common import TimeRange
from app.query.index_router import IndexRouter
from app.semantic.package import CompiledSemanticPackage

PACKAGE_DIR = Path(__file__).parents[4] / "compiled-semantic" / "mock"


def _range(from_month: int, to_month: int) -> TimeRange:
    timezone = ZoneInfo("Asia/Hong_Kong")
    return TimeRange(
        from_inclusive=datetime(2026, from_month, 1, tzinfo=timezone),
        to_exclusive=datetime(2026, to_month, 1, tzinfo=timezone),
        timezone="Asia/Hong_Kong",
    )


def test_may_through_july_routes_exact_months_without_april() -> None:
    package = CompiledSemanticPackage(PACKAGE_DIR)
    router = IndexRouter(
        datasets=package.datasets(), policies=package.policies(), fields=package.fields()
    )
    route = router.route(
        dataset_id="sub_message",
        time_range=_range(5, 8),
        policy_id="mock_business_policy",
        available_indices=package.policies()[0].allowed_index_patterns,
        required_field_ids=("sub_message.event_time", "sub_message.channel"),
    )
    assert route.indices == (
        "tbl_os_sub_message_2026_05",
        "tbl_os_sub_message_2026_06",
        "tbl_os_sub_message_2026_07",
    )
    assert all("_04" not in index for index in route.indices)


def test_partial_mapping_omits_only_incompatible_month() -> None:
    package = CompiledSemanticPackage(PACKAGE_DIR)
    route = IndexRouter(
        datasets=package.datasets(), policies=package.policies(), fields=package.fields()
    ).route(
        dataset_id="sub_message",
        time_range=_range(5, 8),
        policy_id="mock_business_policy",
        available_indices=package.policies()[0].allowed_index_patterns,
        required_field_ids=("sub_message.event_time", "sub_message.latency_ms"),
    )
    assert route.indices == (
        "tbl_os_sub_message_2026_05",
        "tbl_os_sub_message_2026_07",
    )
    assert route.incompatible_indices == ("tbl_os_sub_message_2026_06",)
