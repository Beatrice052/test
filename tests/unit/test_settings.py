from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_default_settings_expose_monthly_scope_and_half_open_time() -> None:
    settings = Settings()

    assert settings.index_scope_label == "tbl_os_sub_message_YYYY_MM"
    assert settings.business_timezone == "Asia/Hong_Kong"
    assert settings.default_time_from.isoformat() == "2026-07-01T00:00:00+08:00"
    assert settings.default_time_to.isoformat() == "2026-08-01T00:00:00+08:00"
    assert "左闭右开" in settings.default_time_range_label


def test_settings_reject_index_pattern_without_month_tokens() -> None:
    with pytest.raises(ValidationError, match="yyyy"):
        Settings(index_pattern="tbl_os_sub_message_current")


def test_settings_reject_naive_or_reversed_time() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Settings(
            default_time_from=datetime.fromisoformat("2026-07-01T00:00:00"),
            default_time_to=datetime.fromisoformat("2026-08-01T00:00:00"),
        )
    with pytest.raises(ValidationError, match="earlier"):
        Settings(
            default_time_from=datetime.fromisoformat("2026-08-01T00:00:00+08:00"),
            default_time_to=datetime.fromisoformat("2026-07-01T00:00:00+08:00"),
        )


def test_settings_reject_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="unknown business timezone"):
        Settings(business_timezone="Moon/Tranquility")
