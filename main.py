"""
Entry point for the daily soccer picks pipeline.

Execution order
---------------
1. Fetch today's match schedule via soccerdata FBref.
2. Generate a prediction for each match (Poisson + Dixon-Coles ensemble).
3. Filter and rank predictions by model confidence.
4. Format the selected picks into a Telegram MarkdownV2 message.
5. Deliver the message via the Telegram Bot API.
6. Persist a JSON record of the run to ``data/history/``.

Run directly (``python main.py``) for a one-shot execution, or invoke via
``scheduler.py`` for time-triggered daily runs.
"""

import logging
import json
from datetime import date, datetime
from config import LOG_LEVEL, LOG_FORMAT, LOG_FILE

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def save_to_history(picks: list, target_date: date, sent: bool) -> None:
    """Persist a daily run record to ``data/history/picks_YYYY-MM-DD.json``.

    The file is written atomically via ``json.dump``; any pre-existing file for
    the same date is overwritten.  Errors are logged but never re-raised so
    that a history write failure cannot abort an otherwise successful run.

    Args:
        picks: Serialisable list of pick dicts that were sent (or attempted).
        target_date: The calendar date the picks correspond to.
        sent: ``True`` when the Telegram message was delivered successfully.
    """
    from config import DATA_HISTORY_DIR

    try:
        filename = DATA_HISTORY_DIR / f"picks_{target_date.strftime('%Y-%m-%d')}.json"
        record = {
            "date": target_date.strftime("%Y-%m-%d"),
            "sent_at": datetime.now().isoformat(),
            "sent": sent,
            "picks": picks,
            "total_picks": len(picks),
        }
        with open(filename, "w") as fh:
            json.dump(record, fh, indent=2, default=str)
        logger.info("History saved: %s", filename)
    except Exception as exc:
        logger.error("Failed to save history: %s", exc)


def main() -> None:
    """Orchestrate the complete daily picks pipeline."""
    from ingestion.calendar import get_matches_today
    from picks.predictor import predict_match
    from picks.filter import filter_picks
    from picks.formatter import format_message
    from telegram.bot import send_message

    today = date.today()
    logger.info("=" * 70)
    logger.info("DAILY PICKS — %s", today)
    logger.info("=" * 70)

    try:
        # ------------------------------------------------------------------
        # Step 1 — fetch today's schedule
        # ------------------------------------------------------------------
        logger.info("Step 1: Fetching today's matches...")
        matches = get_matches_today(today)

        if not matches:
            logger.info("No matches found for today.")
            success = send_message("No matches scheduled today in the configured leagues.")
            save_to_history([], today, success)
            return

        logger.info("Found %d matches.", len(matches))

        # ------------------------------------------------------------------
        # Step 2 — generate predictions
        # ------------------------------------------------------------------
        logger.info("Step 2: Generating predictions for %d matches...", len(matches))
        predictions = []

        for idx, match in enumerate(matches, start=1):
            try:
                logger.info("  [%d/%d] %s vs %s", idx, len(matches), match["home"], match["away"])
                pred = predict_match(match)
                if pred:
                    predictions.append(pred)
                else:
                    logger.warning("    Prediction failed: %s vs %s", match["home"], match["away"])
            except Exception as exc:
                logger.error("    Error predicting %s vs %s: %s", match["home"], match["away"], exc)

        logger.info("Predictions complete: %d / %d succeeded.", len(predictions), len(matches))

        # ------------------------------------------------------------------
        # Step 3 — filter and rank picks
        # ------------------------------------------------------------------
        logger.info("Step 3: Filtering picks...")
        picks = filter_picks(predictions)
        logger.info("Picks selected: %d", len(picks))

        # ------------------------------------------------------------------
        # Step 4 — format Telegram message
        # ------------------------------------------------------------------
        logger.info("Step 4: Formatting message...")
        message = format_message(picks, today)

        # ------------------------------------------------------------------
        # Step 5 — deliver via Telegram
        # ------------------------------------------------------------------
        logger.info("Step 5: Sending via Telegram...")
        success = send_message(message)

        # ------------------------------------------------------------------
        # Step 6 — persist run record
        # ------------------------------------------------------------------
        logger.info("Step 6: Saving history...")
        picks_for_history = [
            {
                "match": p["match"],
                "market": p["market"],
                "probability": p["probability"],
                "confidence": p["confidence"],
            }
            for p in picks
        ]
        save_to_history(picks_for_history, today, success)

        if success:
            logger.info("Daily picks completed successfully.")
        else:
            logger.warning("Picks generated but Telegram delivery failed.")

        logger.info("=" * 70)

    except Exception as exc:
        logger.error("Unexpected error in main pipeline: %s", exc)
        try:
            send_message("An error occurred while generating picks. Will retry tomorrow.")
        except Exception:
            pass
        logger.info("=" * 70)


if __name__ == "__main__":
    main()
