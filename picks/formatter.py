"""
Telegram message formatter.

Renders the daily pick list as a MarkdownV2-formatted string ready for
delivery via the Telegram Bot API.

Telegram's MarkdownV2 mode requires that every special character outside
of intentional markdown syntax is escaped with a backslash.  The
:func:`_escape` helper handles this so that team names or league names
containing dots, dashes, or parentheses don't break the parser.

If the rendered message exceeds ``TELEGRAM_MAX_LENGTH`` characters, picks are
removed one at a time from the bottom of the list until it fits.  The footer
is always preserved so recipients see the model disclaimer.
"""

import logging
from datetime import date
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Telegram MarkdownV2 characters that must be escaped outside markdown syntax.
_MD_SPECIAL = r"\.!()-=[]{}|>#+_*"

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS   = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_SEPARATOR = "────────────────────"


def _escape(text: str) -> str:
    """Escape all MarkdownV2 special characters in *text*.

    Args:
        text: Plain-text string that may contain MarkdownV2 metacharacters.

    Returns:
        The same text with every special character prefixed by ``\\``.
    """
    for ch in _MD_SPECIAL:
        text = text.replace(ch, "\\" + ch)
    return text


def _build_header(target_date: date) -> str:
    """Render the message header for *target_date*.

    Args:
        target_date: The calendar date the picks correspond to.

    Returns:
        MarkdownV2-formatted header string including weekday and date.
    """
    weekday = _WEEKDAYS[target_date.weekday()]
    month   = _MONTHS[target_date.month - 1]
    day     = target_date.day
    year    = target_date.year

    header  = "⚽ *DAILY PICKS*\n"
    header += f"📅 {weekday}, {month} {day}, {year}\n"
    header += f"{_SEPARATOR}\n\n"
    return header


def _build_footer() -> str:
    """Return the standard model disclaimer footer."""
    return (
        "📈 _Picks generated with Poisson \\+ Dixon\\-Coles models_\n"
        "⚠️ _For informational purposes only\\. Bet responsibly\\._"
    )


def _render_pick(pick: Dict) -> str:
    """Render a single pick as a MarkdownV2 block.

    Args:
        pick: A pick dict as produced by :func:`picks.filter.filter_picks`.

    Returns:
        MarkdownV2-formatted string for the pick, including a trailing
        separator line and blank line.
    """
    confidence_emoji = "🟢" if pick["confidence"] == "HIGH" else "🟡"

    match_line  = f"{confidence_emoji} *{_escape(pick['match'])}* — {_escape(pick['league'])}\n"
    time_line   = f"🕒 {_escape(pick['time'])} \\| Pick: *{_escape(pick['market_label'])}*\n"
    prob_line   = f"📊 Probability: {pick['probability']:.0%} \\| Confidence: {pick['confidence']}\n"
    xg_line     = f"⚡ xG: {pick['expected_goals_home']:.2f} — {pick['expected_goals_away']:.2f}\n"
    score_line  = f"🎯 Most likely score: {_escape(pick['top_scoreline'])}\n"

    return match_line + time_line + prob_line + xg_line + score_line + f"\n{_SEPARATOR}\n\n"


def format_message(picks: List[Dict], target_date: Optional[date] = None) -> str:
    """Format the daily pick list into a Telegram-ready MarkdownV2 string.

    If *picks* is empty, a "no picks today" message is returned instead.
    If the assembled message exceeds ``TELEGRAM_MAX_LENGTH``, picks are
    dropped from the bottom until it fits, while the footer is always kept.

    Args:
        picks:       Filtered and ranked pick dicts from :mod:`picks.filter`.
        target_date: Date for the header; defaults to ``date.today()``.

    Returns:
        MarkdownV2-formatted string, guaranteed to be within Telegram's
        character limit.  Returns a plain fallback string on unhandled error.
    """
    from config import TELEGRAM_MAX_LENGTH

    if target_date is None:
        target_date = date.today()

    try:
        header = _build_header(target_date)
        footer = _build_footer()

        if not picks:
            return (
                header
                + "📭 No picks today — no match cleared the confidence threshold\\.\n"
                + f"\n{_SEPARATOR}\n"
                + footer
            )

        body = "".join(_render_pick(p) for p in picks)
        message = header + body + footer

        # Trim picks from the bottom if the message is too long.
        if len(message) > TELEGRAM_MAX_LENGTH:
            logger.warning("Message too long (%d chars); trimming picks.", len(message))
            trimmed = list(picks)
            while len(message) > TELEGRAM_MAX_LENGTH and trimmed:
                trimmed.pop()
                body = "".join(_render_pick(p) for p in trimmed)
                message = header + body + footer

        logger.info("Message formatted: %d chars, %d pick(s).", len(message), len(picks))
        return message

    except Exception as exc:
        logger.error("Error formatting message: %s", exc)
        return "⚽ *ERROR GENERATING PICKS*\nWill retry tomorrow\\."
