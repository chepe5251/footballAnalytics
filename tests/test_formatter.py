"""
Unit tests for picks.formatter.

All tests are offline — no network calls are made.  Each test constructs
minimal pick dicts and asserts structural properties of the output string
(type, length, presence of key substrings).
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from picks.formatter import format_message
from config import TELEGRAM_MAX_LENGTH

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_pick(**overrides) -> dict:
    """Return a minimal valid pick dict, optionally overriding any field."""
    base = {
        "match":               "Arsenal vs Chelsea",
        "league":              "Premier League",
        "time":                "15:00",
        "market":              "over_2_5",
        "market_label":        "Over 2.5 goals",
        "probability":         0.68,
        "confidence":          "HIGH",
        "expected_goals":      2.85,
        "expected_goals_home": 1.72,
        "expected_goals_away": 1.13,
        "top_scoreline":       "2-1",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_picks_returns_string():
    """format_message([]) must return a non-empty string within the Telegram limit."""
    message = format_message([])
    assert isinstance(message, str), "Return type must be str"
    assert len(message) > 0, "Message must not be empty"
    assert len(message) <= TELEGRAM_MAX_LENGTH, "Must respect TELEGRAM_MAX_LENGTH"


def test_empty_picks_mentions_no_picks():
    """The no-picks message must mention that no picks are available."""
    message = format_message([])
    assert "No picks today" in message, "Should inform user that no picks were found"


def test_single_pick_contains_match_info():
    """A message with one pick must contain the match name and probability."""
    message = format_message([_make_pick()], date(2025, 3, 15))
    assert "Arsenal" in message
    assert "Chelsea" in message
    assert "68%" in message


def test_single_pick_within_limit():
    """A single-pick message must be within the Telegram character limit."""
    message = format_message([_make_pick()])
    assert len(message) <= TELEGRAM_MAX_LENGTH


def test_truncation_respects_limit():
    """Messages that would exceed TELEGRAM_MAX_LENGTH must be truncated to fit."""
    picks = [
        _make_pick(match=f"Team {i} vs Team {i + 1}", probability=0.60 + i * 0.001)
        for i in range(20)
    ]
    message = format_message(picks)
    assert len(message) <= TELEGRAM_MAX_LENGTH, (
        f"Message exceeds limit: {len(message)} > {TELEGRAM_MAX_LENGTH}"
    )


def test_footer_always_present():
    """The disclaimer footer must appear in every non-error message."""
    for picks in ([], [_make_pick()]):
        message = format_message(picks)
        assert "Bet responsibly" in message, "Footer disclaimer must always be included"


def test_confidence_emoji_high():
    """HIGH-confidence picks must use the green circle emoji."""
    message = format_message([_make_pick(confidence="HIGH")])
    assert "🟢" in message


def test_confidence_emoji_medium():
    """MEDIUM-confidence picks must use the yellow circle emoji."""
    message = format_message([_make_pick(confidence="MEDIUM")])
    assert "🟡" in message


def test_markdown_escaping_dots():
    """Team names with dots (e.g. A.C. Milan) must not produce unescaped dots."""
    message = format_message([_make_pick(match="A.C. Milan vs AS Roma")])
    assert len(message) > 0, "Message should still be generated"
    # Dots in team names must be backslash-escaped for MarkdownV2.
    assert "\\." in message, "Dots in team names must be escaped"


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("FORMATTER MODULE TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_empty_picks_returns_string,
        test_empty_picks_mentions_no_picks,
        test_single_pick_contains_match_info,
        test_single_pick_within_limit,
        test_truncation_respects_limit,
        test_footer_always_present,
        test_confidence_emoji_high,
        test_confidence_emoji_medium,
        test_markdown_escaping_dots,
    ]

    try:
        for t in tests:
            t()
            print(f"  [PASS] {t.__name__}")
        print("\n[ALL FORMATTER TESTS PASSED]\n")
    except AssertionError as exc:
        print(f"\n[FAILED] {exc}\n")
        sys.exit(1)
