"""Tests for history report formatting."""

from datetime import UTC, datetime
from types import SimpleNamespace

from handlers.history import format_report


def _batch(**overrides):
    values = {
        "total_count": 3,
        "success_count": 1,
        "invalid_count": 1,
        "unknown_count": 1,
        "created_at": datetime(2026, 1, 2, 10, 30, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_report_shows_recorded_counts():
    """The formatted report lists the stored totals exactly."""
    text = format_report(_batch())

    assert "Total checked: 3" in text
    assert "Successful: 1" in text
    assert "Invalid credentials: 1" in text
    assert "Unknown: 1" in text


def test_naive_timestamp_is_treated_as_utc():
    """Timestamps without tzinfo are formatted without raising an error."""
    text = format_report(_batch(created_at=datetime(2026, 1, 2, 10, 30)))

    assert text.startswith("eMaktab Authentication Report\nDate: ")


def test_report_contains_no_credential_like_fields():
    """Only summary lines are rendered, never account labels or secrets."""
    text = format_report(_batch())

    allowed_prefixes = (
        "eMaktab Authentication Report",
        "Date:",
        "Total checked:",
        "Successful:",
        "Invalid credentials:",
        "Unknown:",
    )
    lines = text.splitlines()
    assert len(lines) == 6
    assert all(line.startswith(allowed_prefixes) for line in lines)
