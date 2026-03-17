"""
Feature engineering for match prediction models.

Assembles a flat feature dict from the raw team statistics returned by the
scraper and the match metadata.  Using explicit fallback values for every key
means downstream models always receive a complete, numeric input regardless of
how much live data was available for a given team.
"""

import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)

# League-wide averages used as priors when team-specific data is unavailable.
_LEAGUE_AVG_SCORED = 1.5
_LEAGUE_AVG_CONCEDED = 1.5


def build_features(home_data: Dict, away_data: Dict, match_info: Dict) -> Dict:
    """Construct a feature vector for a single match.

    The returned dict is a flat mapping of feature name → numeric value.
    All keys are guaranteed to be present and finite so that model code can
    index into it without defensive guards.

    Missing or NaN values are replaced by the appropriate league-average prior
    before the dict is returned.

    Args:
        home_data:  Normalised stats dict for the home team (from scraper).
        away_data:  Normalised stats dict for the away team (from scraper).
        match_info: Match metadata dict with at minimum ``"home"`` and
                    ``"away"`` keys.

    Returns:
        Feature dict with keys:

        - ``xg_home_avg``            – home team average xG created
        - ``xg_away_avg``            – away team average xG created
        - ``xga_home_avg``           – home team average xG conceded
        - ``xga_away_avg``           – away team average xG conceded
        - ``form_home``              – home team points per game
        - ``form_away``              – away team points per game
        - ``fatigue_home``           – days since home team's last match
        - ``fatigue_away``           – days since away team's last match
        - ``goals_scored_home_avg``  – home team average goals scored
        - ``goals_conceded_home_avg``– home team average goals conceded
        - ``goals_scored_away_avg``  – away team average goals scored
        - ``goals_conceded_away_avg``– away team average goals conceded
        - ``home_advantage``         – fixed prior (1.0); models may override
    """
    features = {
        "xg_home_avg":             home_data.get("xg_for",         _LEAGUE_AVG_SCORED),
        "xg_away_avg":             away_data.get("xg_for",         _LEAGUE_AVG_SCORED),
        "xga_home_avg":            home_data.get("goals_against",   _LEAGUE_AVG_CONCEDED),
        "xga_away_avg":            away_data.get("goals_against",   _LEAGUE_AVG_CONCEDED),
        "form_home":               home_data.get("form",            1.0),
        "form_away":               away_data.get("form",            1.0),
        "fatigue_home":            home_data.get("days_since_last_match", 7),
        "fatigue_away":            away_data.get("days_since_last_match", 7),
        "goals_scored_home_avg":   home_data.get("goals_for",       _LEAGUE_AVG_SCORED),
        "goals_conceded_home_avg": home_data.get("goals_against",   _LEAGUE_AVG_CONCEDED),
        "goals_scored_away_avg":   away_data.get("goals_for",       _LEAGUE_AVG_SCORED),
        "goals_conceded_away_avg": away_data.get("goals_against",   _LEAGUE_AVG_CONCEDED),
        "home_advantage":          1.0,
    }

    # Replace None / NaN with league-average fallbacks.
    for key, value in features.items():
        if value is None or (isinstance(value, float) and np.isnan(value)):
            features[key] = (
                _LEAGUE_AVG_SCORED
                if ("xg" in key or "goals_scored" in key)
                else _LEAGUE_AVG_CONCEDED
            )

    logger.debug(
        "Features for %s vs %s: %s",
        match_info.get("home"), match_info.get("away"), features,
    )
    return features
