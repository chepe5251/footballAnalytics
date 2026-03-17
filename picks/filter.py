"""
Pick filtering and ranking.

Takes the raw prediction dicts produced by :mod:`picks.predictor`, evaluates
every configured market for every match, and returns a ranked shortlist of
the most confident picks for the day.

Selection criteria
------------------
* The market probability must meet or exceed ``MIN_CONFIDENCE``.
* A maximum of ``MAX_PICKS_PER_DAY`` picks are returned, sorted by
  probability descending so the highest-conviction bets appear first.
* Picks with probability ≥ ``CONFIDENCE_HIGH`` are labelled *HIGH*;
  all others that cleared ``MIN_CONFIDENCE`` are labelled *MEDIUM*.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def filter_picks(predictions: List[Dict]) -> List[Dict]:
    """Filter and rank daily picks from a list of match predictions.

    Args:
        predictions: Raw prediction dicts from :func:`picks.predictor.predict_match`.
                     ``None`` entries are silently skipped.

    Returns:
        A list of pick dicts, sorted by ``probability`` descending and
        capped at ``MAX_PICKS_PER_DAY``.  Returns an empty list on error.

        Each pick dict contains:

        - ``match``                – ``"Home vs Away"`` string
        - ``league``               – human-readable league name
        - ``time``                 – kick-off time (``"HH:MM"``)
        - ``market``               – market key (e.g. ``"home_win"``)
        - ``market_label``         – display label (e.g. ``"Arsenal to win"``)
        - ``probability``          – model probability (4 d.p.)
        - ``confidence``           – ``"HIGH"`` or ``"MEDIUM"``
        - ``expected_goals``       – total xG (home + away)
        - ``expected_goals_home``  – home team xG
        - ``expected_goals_away``  – away team xG
        - ``top_scoreline``        – most likely scoreline string
    """
    from config import (
        CONFIDENCE_HIGH,
        MARKET_LABELS,
        MARKETS,
        MAX_PICKS_PER_DAY,
        MIN_CONFIDENCE,
    )

    picks: List[Dict] = []

    try:
        for pred in predictions:
            if pred is None:
                continue

            match         = pred.get("match", {})
            probs         = pred.get("probabilities", {})
            xg            = pred.get("expected_goals", {})
            top_scorelines = pred.get("top_scorelines", [])

            home   = match.get("home", "")
            away   = match.get("away", "")
            league = match.get("league", "")
            time   = match.get("time", "")

            for market in MARKETS:
                prob = probs.get(market)
                if prob is None or prob < MIN_CONFIDENCE:
                    continue

                confidence = "HIGH" if prob >= CONFIDENCE_HIGH else "MEDIUM"

                # Resolve the display label; fall back to the raw market key.
                label_fn = MARKET_LABELS.get(market)
                market_label = label_fn(home, away) if callable(label_fn) else market

                top_scoreline = (
                    top_scorelines[0].get("score", "1-1")
                    if top_scorelines
                    else "1-1"
                )

                picks.append({
                    "match":               f"{home} vs {away}",
                    "league":              league.split("-")[1].strip() if "-" in league else league,
                    "time":                time,
                    "market":              market,
                    "market_label":        market_label,
                    "probability":         round(prob, 4),
                    "confidence":          confidence,
                    "expected_goals":      round(xg.get("total", 3.0), 2),
                    "expected_goals_home": round(xg.get("home",  1.5), 2),
                    "expected_goals_away": round(xg.get("away",  1.5), 2),
                    "top_scoreline":       top_scoreline,
                })
                logger.debug("Queued pick: %s — %s (%.2f%%)", f"{home} vs {away}", market_label, prob * 100)

        picks.sort(key=lambda p: p["probability"], reverse=True)
        picks = picks[:MAX_PICKS_PER_DAY]

        logger.info("Filtered to %d pick(s).", len(picks))
        return picks

    except Exception as exc:
        logger.error("Error filtering picks: %s", exc)
        return []
