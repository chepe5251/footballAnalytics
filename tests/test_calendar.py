"""
Unit tests for ingestion.calendar.

These tests validate the shape and type guarantees of :func:`get_matches_today`
without making real network calls where possible.  When run against a live
network the test suite degrades gracefully — a day with no fixtures is a
valid outcome, not a failure.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.calendar import get_matches_today


def test_returns_list():
    """get_matches_today must always return a list, never raise."""
    result = get_matches_today()
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_match_schema():
    """Every match dict must contain the required keys with non-empty strings."""
    required_keys = {"home", "away", "league", "date", "time"}
    matches = get_matches_today()

    for match in matches:
        missing = required_keys - match.keys()
        assert not missing, f"Match missing keys: {missing}"
        assert isinstance(match["home"], str) and match["home"], "home must be a non-empty string"
        assert isinstance(match["away"], str) and match["away"], "away must be a non-empty string"
        assert isinstance(match["date"], str), "date must be a string"
        assert isinstance(match["time"], str), "time must be a string"


def test_no_duplicate_fixtures():
    """The same (home, away) pair must not appear more than once per day."""
    matches = get_matches_today()
    seen: set = set()
    for match in matches:
        key = (match["home"], match["away"])
        assert key not in seen, f"Duplicate fixture found: {key}"
        seen.add(key)


def test_never_raises():
    """The function must not propagate any exception to the caller."""
    try:
        get_matches_today()
    except Exception as exc:
        raise AssertionError(f"get_matches_today raised unexpectedly: {exc}")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("CALENDAR MODULE TESTS")
    print("=" * 50 + "\n")

    try:
        test_returns_list()
        print("  [PASS] test_returns_list")

        test_match_schema()
        print("  [PASS] test_match_schema")

        test_no_duplicate_fixtures()
        print("  [PASS] test_no_duplicate_fixtures")

        test_never_raises()
        print("  [PASS] test_never_raises")

        print("\n[ALL CALENDAR TESTS PASSED]\n")
    except AssertionError as exc:
        print(f"\n[FAILED] {exc}\n")
        sys.exit(1)
