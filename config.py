"""
Central configuration for the soccer picks system.

All tunable constants and environment-variable bindings live here.
Import specific names rather than doing ``from config import *`` to keep
dependency surfaces explicit and testable.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
DATA_CACHE_DIR = DATA_DIR / "cache"
DATA_HISTORY_DIR = DATA_DIR / "history"

# Ensure required directories exist at import time (idempotent).
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Telegram credentials  (loaded from .env — never hard-code these)
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Leagues and seasons
# ---------------------------------------------------------------------------

# Leagues are identified by the soccerdata FBref league-code prefix followed
# by a human-readable name, separated by a dash (e.g. "ENG-Premier League").
LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "GER-Bundesliga",
    "ITA-Serie A",
    "FRA-Ligue 1",
]

# Historical seasons used for training and stats scraping.
SEASONS = ["2023-2024", "2024-2025"]

# ---------------------------------------------------------------------------
# Prediction pipeline parameters
# ---------------------------------------------------------------------------

# Number of recent matches used to compute rolling form.
ROLLING_WINDOW = 8

# A pick is only emitted when its model probability meets this floor.
MIN_CONFIDENCE = 0.60

# Hard cap on picks per daily message to keep output concise.
MAX_PICKS_PER_DAY = 5

# Wall-clock time at which the daily pipeline runs (24-hour HH:MM, local tz).
SEND_TIME = "05:00"

# Betting markets evaluated for every match.
MARKETS = [
    "home_win",
    "draw",
    "away_win",
    "over_2_5",
    "btts_yes",
]

# ---------------------------------------------------------------------------
# soccerdata / FBref scraping
# ---------------------------------------------------------------------------

# Set to True to skip local HTML caching (saves disk space; slower retries).
SOCCERDATA_NO_STORE = True

SOCCERDATA_RETRY_MAX = 3   # Maximum attempts per failed request.
SOCCERDATA_SLEEP_MIN = 3   # Minimum jitter delay between requests (seconds).
SOCCERDATA_SLEEP_MAX = 7   # Maximum jitter delay between requests (seconds).

# ---------------------------------------------------------------------------
# Poisson model
# ---------------------------------------------------------------------------

# Multiplicative home-field advantage applied to the home team's lambda.
HOME_ADVANTAGE = 1.25

# ---------------------------------------------------------------------------
# Dixon-Coles model
# ---------------------------------------------------------------------------

# Exponential time-decay coefficient: higher values discount older matches more
# aggressively.  Dixon & Coles (1997) recommend values around 0.0018.
DIXON_COLES_DECAY = 0.0018

# Minimum number of historical matches required before fitting the model.
DIXON_COLES_MIN_MATCHES = 50

# Persisted parameters older than this threshold trigger a re-fit.
DIXON_COLES_RETRAIN_DAYS = 7

# ---------------------------------------------------------------------------
# Ensemble weights  (must sum to 1.0)
# ---------------------------------------------------------------------------

POISSON_WEIGHT = 0.40       # Weight given to the Poisson model output.
DIXON_COLES_WEIGHT = 0.60   # Weight given to the Dixon-Coles model output.

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = PROJECT_ROOT / "soccer_picks.log"

# ---------------------------------------------------------------------------
# Telegram delivery settings
# ---------------------------------------------------------------------------

TELEGRAM_MAX_LENGTH = 4096   # Hard limit imposed by the Telegram Bot API.
TELEGRAM_TIMEOUT = 30        # Per-request connect/read timeout (seconds).
TELEGRAM_RETRY_MAX = 3       # Number of send attempts before giving up.
TELEGRAM_RETRY_DELAY = 5     # Pause between retry attempts (seconds).

# ---------------------------------------------------------------------------
# Market display labels
# ---------------------------------------------------------------------------

# Each value is a callable ``(home: str, away: str) -> str`` so that team
# names can be interpolated into the label at render time.
MARKET_LABELS = {
    "home_win": lambda home, away: f"{home} to win",
    "draw":     lambda home, away: "Draw",
    "away_win": lambda home, away: f"{away} to win",
    "over_2_5": lambda home, away: "Over 2.5 goals",
    "btts_yes": lambda home, away: "Both teams to score",
}

# ---------------------------------------------------------------------------
# Confidence tiers
# ---------------------------------------------------------------------------

CONFIDENCE_HIGH = 0.70    # Probability >= 70 % → HIGH confidence.
CONFIDENCE_MEDIUM = 0.60  # Probability >= 60 % → MEDIUM confidence.
