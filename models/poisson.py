"""
Double-Poisson match prediction model.

Models each team's goal output as an independent Poisson process whose rate
parameter (lambda) is derived from the team's attack strength, the opponent's
defensive weakness, a league-average baseline, and a home-field advantage
multiplier.

Scoreline probabilities are computed over a 9×9 grid (0–8 goals per side),
which covers > 99 % of real-match outcomes.  Aggregated market probabilities
(1X2, over/under, BTTS) are derived from that grid.

Reference
---------
Maher, M. J. (1982). Modelling association football scores.
*Statistica Neerlandica*, 36(3), 109–118.
"""

import logging
from typing import Dict, List

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# Score-grid dimension: probabilities are computed for 0..MAX_GOALS goals.
_MAX_GOALS = 8


def _under_count(probs: np.ndarray, goals: int) -> float:
    """Return the probability of *goals* or fewer total goals in the match.

    This is the cumulative probability for all (i, j) where i + j <= goals,
    as used for Over/Under markets.

    Args:
        probs: 9×9 joint-probability matrix (home goals × away goals).
        goals: Total-goals ceiling (inclusive).
    """
    total = 0.0
    for i in range(goals + 1):
        for j in range(goals + 1 - i):
            total += probs[i, j]
    return total


class PoissonModel:
    """Double-Poisson model for soccer match outcome prediction.

    The model expresses each team's expected goals (λ) as:

        λ_home = attack_home × defense_away × league_avg × home_advantage
        λ_away = attack_away × defense_home × league_avg

    where attack and defense strengths are ratios relative to the league
    average, so a perfectly average team has attack = defense = 1.0.
    """

    def __init__(self, home_advantage: float = 1.25, league_avg_goals: float = 1.5) -> None:
        """
        Args:
            home_advantage:   Multiplicative boost applied to the home team's λ.
            league_avg_goals: Prior for the average number of goals per team
                              per match in the target league.
        """
        self.home_advantage = home_advantage
        self.league_avg_goals = league_avg_goals

    def predict(self, home_data: Dict, away_data: Dict) -> Dict:
        """Compute match-outcome probabilities from team feature dicts.

        Args:
            home_data: Feature dict for the home team (keys: ``xg_for``,
                       ``goals_against``).
            away_data: Feature dict for the away team (same keys).

        Returns:
            Prediction dict containing:

            - ``lambda_home`` / ``lambda_away`` – expected goals per side
            - ``home_win``, ``draw``, ``away_win`` – 1X2 probabilities
            - ``over_0_5`` … ``over_3_5`` – over-goals market probabilities
            - ``btts_yes`` / ``btts_no`` – both-teams-to-score probabilities
            - ``expected_goals_total`` – sum of both lambdas
            - ``top_scorelines`` – up to 5 most likely scorelines (≥ 1 %)

            On any unhandled exception, neutral (uniform 1X2) probabilities
            are returned so the pipeline can continue.
        """
        try:
            xg_home = max(0.1, home_data.get("xg_for", 1.5))
            xga_home = max(0.1, home_data.get("goals_against", 1.5))
            xg_away = max(0.1, away_data.get("xg_for", 1.5))
            xga_away = max(0.1, away_data.get("goals_against", 1.5))

            # Normalise attack/defense relative to the league average.
            attack_home = xg_home / self.league_avg_goals
            defense_home = xga_home / self.league_avg_goals
            attack_away = xg_away / self.league_avg_goals
            defense_away = xga_away / self.league_avg_goals

            lambda_home = max(0.1, attack_home * defense_away * self.league_avg_goals * self.home_advantage)
            lambda_away = max(0.1, attack_away * defense_home * self.league_avg_goals)

            # Build the 9×9 joint-probability matrix.
            size = _MAX_GOALS + 1
            probs = np.zeros((size, size))
            for i in range(size):
                for j in range(size):
                    probs[i, j] = (
                        stats.poisson.pmf(i, lambda_home)
                        * stats.poisson.pmf(j, lambda_away)
                    )

            # 1X2 probabilities.
            home_win = float(np.sum(np.triu(probs, k=1)))   # home goals > away
            draw     = float(np.sum(np.diag(probs)))         # home goals == away
            away_win = float(np.sum(np.tril(probs, k=-1)))  # home goals < away

            # Over/Under markets (note: _under_count sums over total goals, not
            # each side independently — corrected from the original per-side sum).
            over_0_5 = 1.0 - _under_count(probs, 0)
            over_1_5 = 1.0 - _under_count(probs, 1)
            over_2_5 = 1.0 - _under_count(probs, 2)
            over_3_5 = 1.0 - _under_count(probs, 3)

            # BTTS: P(home ≥ 1) × P(away ≥ 1) = 1 − P(home=0) − P(away=0) + P(0-0)
            btts_yes = 1.0 - float(np.sum(probs[0, :])) - float(np.sum(probs[:, 0])) + probs[0, 0]
            btts_no  = 1.0 - btts_yes

            # Top-5 most likely scorelines with probability ≥ 1 %.
            flat      = probs.flatten()
            top_idx   = np.argsort(-flat)[:5]
            top_scorelines: List[Dict] = []
            for idx in top_idx:
                i, j = divmod(int(idx), size)
                if probs[i, j] >= 0.01:
                    top_scorelines.append({"score": f"{i}-{j}", "prob": float(probs[i, j])})

            result = {
                "lambda_home":          float(lambda_home),
                "lambda_away":          float(lambda_away),
                "home_win":             float(np.clip(home_win, 0, 1)),
                "draw":                 float(np.clip(draw,     0, 1)),
                "away_win":             float(np.clip(away_win, 0, 1)),
                "over_0_5":             float(np.clip(over_0_5, 0, 1)),
                "over_1_5":             float(np.clip(over_1_5, 0, 1)),
                "over_2_5":             float(np.clip(over_2_5, 0, 1)),
                "over_3_5":             float(np.clip(over_3_5, 0, 1)),
                "btts_yes":             float(np.clip(btts_yes, 0, 1)),
                "btts_no":              float(np.clip(btts_no,  0, 1)),
                "expected_goals_total": float(lambda_home + lambda_away),
                "top_scorelines":       top_scorelines,
            }

            logger.debug("Poisson prediction: %s", result)
            return result

        except Exception as exc:
            logger.error("Poisson prediction failed: %s", exc)
            return _neutral_prediction()


def _neutral_prediction() -> Dict:
    """Return uniform 1X2 probabilities used as a safe fallback."""
    return {
        "lambda_home":          1.5,
        "lambda_away":          1.5,
        "home_win":             0.33,
        "draw":                 0.33,
        "away_win":             0.33,
        "over_0_5":             0.95,
        "over_1_5":             0.80,
        "over_2_5":             0.50,
        "over_3_5":             0.20,
        "btts_yes":             0.40,
        "btts_no":              0.60,
        "expected_goals_total": 3.0,
        "top_scorelines":       [{"score": "1-1", "prob": 0.10}],
    }
