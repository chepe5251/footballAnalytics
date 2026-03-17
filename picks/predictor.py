"""
Match prediction orchestrator.

Combines the Poisson and Dixon-Coles models into a weighted ensemble for a
single match.  The pipeline is:

1. Scrape team statistics from FBref via :mod:`ingestion.scraper`.
2. Build a normalised feature dict via :mod:`features.builder`.
3. Run the Poisson model (always available; no pre-training required).
4. Attempt a Dixon-Coles prediction if persisted parameters exist and are
   fresh enough; otherwise the ensemble falls back to Poisson-only.
5. Blend both predictions with ``POISSON_WEIGHT`` / ``DIXON_COLES_WEIGHT``
   from config and return a structured result dict.

The function never raises; any unhandled exception results in ``None`` so
the caller can skip this match gracefully.
"""

import logging
from typing import Dict, Optional

from features.builder import build_features
from ingestion.scraper import get_team_data
from models.dixon_coles import DixonColesModel
from models.poisson import PoissonModel

logger = logging.getLogger(__name__)

# Fallback team-data stub used when scraping fails entirely.
_FALLBACK_TEAM_DATA = {"xg_for": 1.5, "goals_against": 1.5, "incomplete": True}


def predict_match(match_info: Dict) -> Optional[Dict]:
    """Generate a complete prediction for a single match.

    Args:
        match_info: Dict with keys ``home``, ``away``, ``league``, ``date``,
                    and ``time`` (all strings).

    Returns:
        A prediction dict on success, or ``None`` if the pipeline fails.

        The dict contains:

        - ``match``           – echo of the input match metadata
        - ``probabilities``   – ensemble probabilities for each market key
        - ``expected_goals``  – ``{home, away, total}`` lambda values
        - ``top_scorelines``  – ranked list of ``{score, prob}`` dicts
        - ``model_used``      – ``"ensemble"`` or ``"poisson_only"``
        - ``data_complete``   – ``False`` if any scraping step was partial
    """
    from config import DIXON_COLES_WEIGHT, POISSON_WEIGHT, SEASONS

    home_team = match_info.get("home", "")
    away_team = match_info.get("away", "")
    league    = match_info.get("league", "")
    league_code = league.split("-")[0].strip() if "-" in league else league

    logger.info("Predicting: %s vs %s (%s)", home_team, away_team, league)

    # ------------------------------------------------------------------
    # Step 1 — scrape team statistics
    # ------------------------------------------------------------------
    try:
        home_data = get_team_data(home_team, league_code, SEASONS)
        away_data = get_team_data(away_team, league_code, SEASONS)
        data_complete = not (home_data.get("incomplete") or away_data.get("incomplete"))
    except Exception as exc:
        logger.warning("Scraping failed for %s vs %s: %s", home_team, away_team, exc)
        home_data, away_data = _FALLBACK_TEAM_DATA.copy(), _FALLBACK_TEAM_DATA.copy()
        data_complete = False

    # ------------------------------------------------------------------
    # Step 2 — build features
    # ------------------------------------------------------------------
    try:
        build_features(home_data, away_data, match_info)
    except Exception as exc:
        logger.error("Feature engineering failed: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Step 3 — Poisson prediction
    # ------------------------------------------------------------------
    try:
        poisson_pred = PoissonModel().predict(home_data, away_data)
    except Exception as exc:
        logger.error("Poisson prediction failed: %s", exc)
        poisson_pred = None

    # ------------------------------------------------------------------
    # Step 4 — Dixon-Coles prediction (optional)
    # ------------------------------------------------------------------
    dc_pred = None
    try:
        dc_model = DixonColesModel()
        if dc_model.load_params(league_code):
            dc_pred = dc_model.predict(home_team, away_team)
        else:
            logger.debug("Dixon-Coles parameters unavailable for '%s'.", league_code)
    except Exception as exc:
        logger.debug("Dixon-Coles prediction skipped: %s", exc)

    # ------------------------------------------------------------------
    # Step 5 — ensemble
    # ------------------------------------------------------------------
    if poisson_pred is None:
        logger.error("All prediction models failed for %s vs %s.", home_team, away_team)
        return None

    markets = ("home_win", "draw", "away_win", "over_2_5", "btts_yes")

    if dc_pred:
        model_used = "ensemble"
        ensemble_probs = {
            m: poisson_pred[m] * POISSON_WEIGHT + dc_pred[m] * DIXON_COLES_WEIGHT
            for m in markets
        }
        xg_total = (
            poisson_pred["expected_goals_total"] * POISSON_WEIGHT
            + dc_pred["expected_goals_total"] * DIXON_COLES_WEIGHT
        )
    else:
        model_used = "poisson_only"
        ensemble_probs = {m: poisson_pred[m] for m in markets}
        xg_total = poisson_pred["expected_goals_total"]

    return {
        "match": {
            "home":   home_team,
            "away":   away_team,
            "league": league,
            "date":   match_info.get("date", ""),
            "time":   match_info.get("time", ""),
        },
        "probabilities": ensemble_probs,
        "expected_goals": {
            "home":  float(poisson_pred.get("lambda_home", 1.5)),
            "away":  float(poisson_pred.get("lambda_away", 1.5)),
            "total": float(xg_total),
        },
        "top_scorelines": poisson_pred.get("top_scorelines", []),
        "model_used":     model_used,
        "data_complete":  data_complete,
    }
