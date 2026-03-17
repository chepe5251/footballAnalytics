"""
Match calendar ingestion.

Fetches the daily fixture list from soccerdata's FBref adapter across all
configured leagues and seasons, returning a normalised list of match dicts
ready for the prediction pipeline.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
import soccerdata as sd

logger = logging.getLogger(__name__)


def get_matches_today(target_date: Optional[date] = None) -> List[Dict]:
    """Return all fixtures scheduled on *target_date* across configured leagues.

    The function queries each league/season combination and de-duplicates
    results by (home, away, date) so that the same fixture is never returned
    twice if it appears in more than one season's schedule.

    Args:
        target_date: The date to look up.  Defaults to ``date.today()``.

    Returns:
        A list of match dicts, each containing:

        - ``home``   – home team name
        - ``away``   – away team name
        - ``league`` – full league identifier (e.g. ``"ENG-Premier League"``)
        - ``date``   – ISO-8601 date string (``"YYYY-MM-DD"``)
        - ``time``   – kick-off time string (``"HH:MM"``)
    """
    from config import LEAGUES, SEASONS

    if target_date is None:
        target_date = date.today()

    target_str = target_date.strftime("%Y-%m-%d")
    matches: List[Dict] = []
    seen: set = set()  # (home, away) pairs already added

    for league in LEAGUES:
        try:
            league_code = league.split("-")[0].strip()
            logger.info("Fetching schedule: %s for %s", league, target_str)

            for season in SEASONS:
                try:
                    df = sd.FBref.read_schedule(league_code, season=season)
                    if df is None or df.empty:
                        continue

                    if "Date" not in df.columns:
                        continue

                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    day_df = df[df["Date"].dt.date == target_date]

                    for _, row in day_df.iterrows():
                        try:
                            home = row.get("Home", "")
                            away = row.get("Away", "")
                            if not home or not away:
                                continue

                            key = (home, away)
                            if key in seen:
                                continue
                            seen.add(key)

                            matches.append({
                                "home": home,
                                "away": away,
                                "league": league,
                                "date": target_str,
                                "time": str(row.get("Time", "00:00"))[:5],
                            })
                            logger.debug("Queued match: %s vs %s", home, away)
                        except Exception as exc:
                            logger.warning("Skipping malformed row: %s", exc)

                except Exception as exc:
                    logger.debug("No data for %s %s: %s", league_code, season, exc)

        except Exception as exc:
            logger.error("Error fetching schedule for %s: %s", league, exc)

    logger.info("Found %d matches for %s.", len(matches), target_str)
    return matches
