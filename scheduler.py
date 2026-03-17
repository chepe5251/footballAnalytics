"""
Background scheduler for the daily picks pipeline.

Wraps the ``schedule`` library to trigger ``main.py`` once per day at the
wall-clock time configured in ``config.SEND_TIME``.

Usage
-----
Start the long-running process::

    python scheduler.py

Run immediately and then keep the scheduler active::

    python scheduler.py --now
"""

import logging
import time
import subprocess
import argparse
from datetime import datetime
import schedule
from config import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def run_daily_picks() -> None:
    """Invoke ``main.py`` in a subprocess and log the outcome.

    Running main.py as a subprocess rather than importing it directly provides
    a clean process boundary: uncaught exceptions or memory leaks in the
    pipeline cannot corrupt the long-running scheduler process.
    """
    logger.info("=" * 60)
    logger.info("RUNNING DAILY PICKS — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    try:
        result = subprocess.run(["python", "main.py"], text=True)
        if result.returncode == 0:
            logger.info("Daily picks completed successfully.")
        else:
            logger.error("Daily picks exited with code %d.", result.returncode)
    except Exception as exc:
        logger.error("Failed to launch daily picks subprocess: %s", exc)

    logger.info("=" * 60)


def main() -> None:
    """Parse arguments, configure the schedule, and enter the event loop."""
    from config import SEND_TIME

    parser = argparse.ArgumentParser(description="Daily soccer picks scheduler.")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Execute the pipeline immediately, then resume normal scheduling.",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SCHEDULER STARTED — daily run at %s", SEND_TIME)
    logger.info("=" * 60)

    if args.now:
        logger.info("--now flag detected; running pipeline immediately.")
        run_daily_picks()

    schedule.every().day.at(SEND_TIME).do(run_daily_picks)
    logger.info("Scheduler active. Next run at %s.", SEND_TIME)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Poll resolution: one minute is sufficient.
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user (SIGINT).")
    except Exception as exc:
        logger.error("Unexpected error in scheduler loop: %s", exc)


if __name__ == "__main__":
    main()
