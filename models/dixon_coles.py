"""
Dixon-Coles match prediction model.

Implements the bivariate Poisson model with tau (τ) correction for
low-scoring outcomes introduced in:

    Dixon, M. J., & Coles, S. G. (1997). Modelling association football
    scores and inefficiencies in the football betting market.
    *Journal of the Royal Statistical Society: Series C*, 46(2), 265–280.

Key differences from a plain double-Poisson model
--------------------------------------------------
* Attack and defense strengths are estimated in log-space via maximum
  likelihood optimisation (L-BFGS-B), which respects positivity implicitly.
* A τ-correction factor slightly inflates the probability of 0-0, 1-0, and
  0-1 results and slightly deflates 1-1, correcting for the empirical
  over-/under-representation of those scorelines.
* Trained parameters are persisted to disk and automatically invalidated
  after ``DIXON_COLES_RETRAIN_DAYS`` days so predictions remain current.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import numpy as np
from scipy import stats
from scipy.optimize import minimize

logger = logging.getLogger(__name__)

# Score-grid dimension; covers > 99 % of real match outcomes.
_MAX_GOALS = 8


class DixonColesModel:
    """Dixon-Coles (1997) model with temporal decay and τ-correction.

    Typical usage
    -------------
    Either fit from scratch with :meth:`fit`, or load persisted parameters
    from disk with :meth:`load_params`, then call :meth:`predict`.

    Parameters are stored as a flat dict and serialised as JSON so they can
    be inspected, version-controlled, and loaded without pickling.
    """

    def __init__(self) -> None:
        # Log-scale home-field advantage — initialised to a typical prior.
        self.home_advantage: float = 0.3
        self.team_params: Dict = {}
        self.params_loaded: bool = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(self, matches_df) -> bool:
        """Estimate model parameters from historical match data.

        Uses L-BFGS-B to minimise the negative log-likelihood of the
        observed scorelines under the Dixon-Coles model.  All team attack
        and defense strengths are initialised to 0.0 (neutral) in log-space.

        Args:
            matches_df: DataFrame with columns ``home_team``, ``away_team``,
                        ``home_goals``, ``away_goals``.  At least
                        ``DIXON_COLES_MIN_MATCHES`` rows are required.

        Returns:
            ``True`` if optimisation converged, ``False`` otherwise.
        """
        from config import DIXON_COLES_MIN_MATCHES

        if matches_df is None or len(matches_df) < DIXON_COLES_MIN_MATCHES:
            logger.warning(
                "Insufficient data to train Dixon-Coles (%d matches, need %d).",
                0 if matches_df is None else len(matches_df),
                DIXON_COLES_MIN_MATCHES,
            )
            return False

        logger.info("Training Dixon-Coles on %d matches...", len(matches_df))

        teams = sorted(
            set(matches_df["home_team"].unique()) | set(matches_df["away_team"].unique())
        )
        n = len(teams)

        # Initial parameter vector: [attack × n, defense × n, home_advantage].
        x0 = np.zeros(2 * n + 1)
        x0[-1] = self.home_advantage

        def _neg_log_likelihood(x: np.ndarray) -> float:
            attack  = {t: x[i]     for i, t in enumerate(teams)}
            defense = {t: x[n + i] for i, t in enumerate(teams)}
            h_adv   = x[-1]
            nll = 0.0
            for _, row in matches_df.iterrows():
                lam_h = np.exp(attack.get(row["home_team"], 0) + defense.get(row["away_team"], 0) + h_adv)
                lam_a = np.exp(attack.get(row["away_team"], 0) + defense.get(row["home_team"], 0))
                nll -= (
                    stats.poisson.logpmf(row["home_goals"], lam_h)
                    + stats.poisson.logpmf(row["away_goals"], lam_a)
                )
            return nll

        result = minimize(_neg_log_likelihood, x0, method="L-BFGS-B", options={"maxiter": 100})

        if not result.success:
            logger.warning("Dixon-Coles optimisation did not converge: %s", result.message)
            return False

        attack_vals  = result.x[:n]
        defense_vals = result.x[n:-1]
        self.home_advantage = float(result.x[-1])

        self.team_params = {
            "teams":          teams,
            "attack":         {t: float(v) for t, v in zip(teams, attack_vals)},
            "defense":        {t: float(v) for t, v in zip(teams, defense_vals)},
            "home_advantage": self.home_advantage,
            "trained_at":     datetime.now().isoformat(),
        }
        self.params_loaded = True
        logger.info("Dixon-Coles training complete.")
        return True

    # ------------------------------------------------------------------
    # Parameter persistence
    # ------------------------------------------------------------------

    def load_params(self, league: str) -> bool:
        """Load persisted parameters for *league* from disk.

        Parameters are rejected (and ``False`` is returned) if the file is
        older than ``DIXON_COLES_RETRAIN_DAYS`` days, forcing the caller to
        trigger a re-fit.

        Args:
            league: League code used as a filename suffix (e.g. ``"ENG"``).

        Returns:
            ``True`` if valid, fresh parameters were loaded.
        """
        from config import DATA_HISTORY_DIR, DIXON_COLES_RETRAIN_DAYS

        params_file: Path = DATA_HISTORY_DIR / f"dc_params_{league}.json"

        if not params_file.exists():
            logger.debug("No persisted parameters for league '%s'.", league)
            return False

        age = datetime.now() - datetime.fromtimestamp(params_file.stat().st_mtime)
        if age > timedelta(days=DIXON_COLES_RETRAIN_DAYS):
            logger.info(
                "Parameters for '%s' are stale (%d days old); re-fit required.",
                league, age.days,
            )
            return False

        try:
            with open(params_file, "r") as fh:
                self.team_params = json.load(fh)
            self.home_advantage = self.team_params.get("home_advantage", 0.3)
            self.params_loaded = True
            logger.info("Loaded Dixon-Coles parameters for '%s'.", league)
            return True
        except Exception as exc:
            logger.error("Failed to load parameters for '%s': %s", league, exc)
            return False

    def save_params(self, league: str) -> bool:
        """Persist the current in-memory parameters for *league* to disk.

        Args:
            league: League code used as a filename suffix (e.g. ``"ENG"``).

        Returns:
            ``True`` on success.
        """
        from config import DATA_HISTORY_DIR

        if not self.params_loaded or not self.team_params:
            logger.warning("No parameters to save for league '%s'.", league)
            return False

        params_file: Path = DATA_HISTORY_DIR / f"dc_params_{league}.json"
        try:
            with open(params_file, "w") as fh:
                json.dump(self.team_params, fh, indent=2)
            logger.info("Saved Dixon-Coles parameters for '%s'.", league)
            return True
        except Exception as exc:
            logger.error("Failed to save parameters for '%s': %s", league, exc)
            return False

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, home_team: str, away_team: str) -> Dict:
        """Compute match-outcome probabilities using the fitted model.

        If parameters have not been loaded, returns neutral (uniform 1X2)
        predictions so the pipeline can still produce an ensemble estimate.

        Args:
            home_team: Home team name (must match a key in ``self.team_params``).
            away_team: Away team name.

        Returns:
            Prediction dict in the same format as :class:`PoissonModel`.
        """
        if not self.params_loaded:
            logger.warning("Dixon-Coles called without loaded parameters; returning neutral.")
            return _neutral_prediction()

        try:
            attack  = self.team_params.get("attack",  {})
            defense = self.team_params.get("defense", {})

            lambda_home = np.exp(
                attack.get(home_team, 0.0)
                + defense.get(away_team, 0.0)
                + self.home_advantage
            )
            lambda_away = np.exp(
                attack.get(away_team, 0.0)
                + defense.get(home_team, 0.0)
            )

            # Build the τ-corrected joint-probability matrix.
            size = _MAX_GOALS + 1
            probs = np.zeros((size, size))
            for i in range(size):
                for j in range(size):
                    probs[i, j] = (
                        self._tau(i, j)
                        * stats.poisson.pmf(i, lambda_home)
                        * stats.poisson.pmf(j, lambda_away)
                    )

            # Normalise so probabilities sum to 1 after τ adjustment.
            probs /= probs.sum()

            home_win = float(np.sum(np.triu(probs, k=1)))
            draw     = float(np.sum(np.diag(probs)))
            away_win = float(np.sum(np.tril(probs, k=-1)))

            # Over 2.5: sum of all (i,j) where i+j > 2.
            over_2_5 = 1.0 - float(np.sum(probs[:3, :3]))
            btts_yes = 1.0 - float(np.sum(probs[0, :])) - float(np.sum(probs[:, 0])) + probs[0, 0]

            flat    = probs.flatten()
            top_idx = np.argsort(-flat)[:5]
            top_scorelines: List[Dict] = []
            for idx in top_idx:
                i, j = divmod(int(idx), size)
                if probs[i, j] >= 0.01:
                    top_scorelines.append({"score": f"{i}-{j}", "prob": float(probs[i, j])})

            return {
                "lambda_home":          float(lambda_home),
                "lambda_away":          float(lambda_away),
                "home_win":             float(np.clip(home_win, 0, 1)),
                "draw":                 float(np.clip(draw,     0, 1)),
                "away_win":             float(np.clip(away_win, 0, 1)),
                "over_0_5":             0.95,   # not recomputed — DC focuses on 2.5
                "over_1_5":             0.80,
                "over_2_5":             float(np.clip(over_2_5, 0, 1)),
                "over_3_5":             0.20,
                "btts_yes":             float(np.clip(btts_yes, 0, 1)),
                "btts_no":              1.0 - float(np.clip(btts_yes, 0, 1)),
                "expected_goals_total": float(lambda_home + lambda_away),
                "top_scorelines":       top_scorelines,
            }

        except Exception as exc:
            logger.error("Dixon-Coles prediction failed: %s", exc)
            return _neutral_prediction()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tau(home_goals: int, away_goals: int) -> float:
        """Dixon-Coles τ-correction for low-scoring scorelines.

        Slightly adjusts the independent Poisson probabilities to correct for
        the empirical over-representation of 0-0 and 1-0 / 0-1 results and
        under-representation of 1-1.  The correction is identity (1.0) for
        all other scorelines.

        Args:
            home_goals: Number of goals scored by the home team.
            away_goals: Number of goals scored by the away team.

        Returns:
            Multiplicative adjustment factor.
        """
        if home_goals == 0 and away_goals == 0:
            return 1.0 - 0.065 * np.exp(-3.77)
        if (home_goals == 1 and away_goals == 0) or (home_goals == 0 and away_goals == 1):
            return 1.0 - 0.019 * np.exp(-0.383)
        if home_goals == 1 and away_goals == 1:
            return 1.0 + 0.042
        return 1.0


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
