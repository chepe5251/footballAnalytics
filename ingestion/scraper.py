"""
Team statistics scraper.

Fetches per-team shooting and playing-time data from soccerdata's FBref
adapter.  Each call applies jitter-based rate limiting and exponential-backoff
retries to stay within FBref's request budget.

Returned stats are *per-match averages* normalised over a rolling window,
not raw season totals, so they can be fed directly into the prediction models.
"""

import logging
import random
import time
from typing import Dict, List

import pandas as pd
import soccerdata as sd

logger = logging.getLogger(__name__)


def get_team_data(team: str, league: str, seasons: List[str]) -> Dict:
    """Fetch and normalise team statistics from FBref across one or more seasons.

    The function queries the *playing_time* and *shooting* stat tables for
    each season in ``seasons``, accumulates the best (highest) values found,
    and finally converts season totals to per-match averages over
    ``ROLLING_WINDOW`` matches.

    When a request fails the function retries up to ``SOCCERDATA_RETRY_MAX``
    times with an exponential back-off delay.  If all retries are exhausted,
    the ``incomplete`` flag is set to ``True`` so downstream code can decide
    whether to skip or weight-down the prediction.

    Args:
        team:    Team name as it appears in FBref (e.g. ``"Arsenal"``).
        league:  Full league identifier (e.g. ``"ENG-Premier League"``).
                 Only the prefix before the dash is sent to soccerdata.
        seasons: Ordered list of season strings to query (e.g.
                 ``["2023-2024", "2024-2025"]``).

    Returns:
        A dict with the following keys:

        - ``xg_for``               – average xG created per match
        - ``xga``                  – average xG conceded per match (placeholder)
        - ``goals_for``            – average goals scored per match
        - ``goals_against``        – average goals conceded per match
        - ``form``                 – points per game (default 1.0 when unknown)
        - ``games_played``         – total matches found across all seasons
        - ``days_since_last_match``– fatigue proxy (default 7 when unknown)
        - ``incomplete``           – ``True`` if any season failed all retries
    """
    from config import ROLLING_WINDOW, SOCCERDATA_RETRY_MAX, SOCCERDATA_SLEEP_MIN, SOCCERDATA_SLEEP_MAX

    stats: Dict = {
        "xg_for": 0.0,
        "xga": 0.0,
        "goals_for": 0.0,
        "goals_against": 0.0,
        "form": 1.0,
        "games_played": 0,
        "days_since_last_match": 7,
        "incomplete": False,
    }

    # soccerdata expects only the two-letter prefix (e.g. "ENG").
    league_code = league.split("-")[0].strip()

    for season in seasons:
        attempt = 0
        while attempt < SOCCERDATA_RETRY_MAX:
            try:
                # Jitter delay to avoid triggering FBref rate limits.
                time.sleep(random.uniform(SOCCERDATA_SLEEP_MIN, SOCCERDATA_SLEEP_MAX))

                logger.info("Fetching %s | %s | %s...", team, league_code, season)

                playing_df = sd.FBref.read_team_data(
                    league_code, season=season, stat_type="playing_time"
                )
                if playing_df is None or playing_df.empty:
                    logger.debug("No playing-time data for %s in %s.", team, season)
                    attempt += 1
                    continue

                team_row = playing_df[
                    playing_df["Squad"].str.contains(team, case=False, na=False)
                ]
                if team_row.empty:
                    logger.debug("Team '%s' not found in %s %s.", team, league_code, season)
                    attempt += 1
                    continue

                # --- Shooting stats (xG, goals) ---
                try:
                    shooting_df = sd.FBref.read_team_data(
                        league_code, season=season, stat_type="shooting"
                    )
                    if shooting_df is not None and not shooting_df.empty:
                        team_shooting = shooting_df[
                            shooting_df["Squad"].str.contains(team, case=False, na=False)
                        ]
                        if not team_shooting.empty:
                            if "xG" in team_shooting.columns:
                                val = team_shooting["xG"].iloc[0]
                                stats["xg_for"] = max(
                                    stats["xg_for"],
                                    float(val) if pd.notna(val) else 0.0,
                                )
                            if "G" in team_shooting.columns:
                                val = team_shooting["G"].iloc[0]
                                stats["goals_for"] = max(
                                    stats["goals_for"],
                                    float(val) if pd.notna(val) else 0.0,
                                )
                except Exception as exc:
                    logger.debug("Could not fetch shooting stats for %s: %s", team, exc)

                # --- Goals for / against / matches played ---
                try:
                    for col, key in [("GF", "goals_for"), ("GA", "goals_against")]:
                        if col in team_row.columns:
                            val = team_row[col].iloc[0]
                            stats[key] = max(
                                stats[key],
                                float(val) if pd.notna(val) else 0.0,
                            )
                    if "Matches" in team_row.columns:
                        val = team_row["Matches"].iloc[0]
                        stats["games_played"] = max(
                            stats["games_played"],
                            int(val) if pd.notna(val) else 0,
                        )
                except Exception as exc:
                    logger.debug("Error extracting core stats for %s: %s", team, exc)

                logger.debug("Successfully fetched %s from %s.", team, season)
                break  # Season succeeded — move on to the next one.

            except Exception as exc:
                attempt += 1
                if attempt < SOCCERDATA_RETRY_MAX:
                    backoff = 2 ** attempt
                    logger.warning(
                        "Retry %d/%d for %s in %s (waiting %ds): %s",
                        attempt, SOCCERDATA_RETRY_MAX, team, season, backoff, exc,
                    )
                    time.sleep(backoff)
                else:
                    logger.error("All retries exhausted for %s in %s: %s", team, season, exc)
                    stats["incomplete"] = True

    # Convert raw season totals → per-match averages over the rolling window.
    if stats["games_played"] > 0:
        window_ratio = max(1, stats["games_played"] / ROLLING_WINDOW)
        stats["xg_for"] = stats["xg_for"] / window_ratio
        stats["goals_for"] = stats["goals_for"] / window_ratio
        stats["goals_against"] = stats["goals_against"] / window_ratio

    logger.info("Stats for %s: %s", team, stats)
    return stats
