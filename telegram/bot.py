"""
Telegram delivery module.

Provides thin synchronous wrappers around the async python-telegram-bot
``Bot`` client.  All network I/O happens inside async coroutines; the public
API is synchronous so callers don't need to manage an event loop.

Retry behaviour
---------------
Transient ``TelegramError`` exceptions trigger up to ``TELEGRAM_RETRY_MAX``
retries with a fixed ``TELEGRAM_RETRY_DELAY`` pause between attempts.
Non-Telegram exceptions (e.g. network stack errors) are treated as fatal for
that call and logged immediately.
"""

import asyncio
import logging
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


async def _send_async(text: str) -> bool:
    """Send *text* to the configured chat, retrying on transient errors.

    Args:
        text: MarkdownV2-formatted message body.

    Returns:
        ``True`` on delivery, ``False`` after exhausting all retry attempts.
    """
    from config import (
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
        TELEGRAM_TIMEOUT,
        TELEGRAM_RETRY_MAX,
        TELEGRAM_RETRY_DELAY,
    )

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        return False

    bot = Bot(token=TELEGRAM_TOKEN)

    for attempt in range(1, TELEGRAM_RETRY_MAX + 1):
        try:
            logger.info("Sending Telegram message (attempt %d/%d)...", attempt, TELEGRAM_RETRY_MAX)
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=text,
                parse_mode="MarkdownV2",
                connect_timeout=TELEGRAM_TIMEOUT,
                read_timeout=TELEGRAM_TIMEOUT,
            )
            logger.info("Telegram message delivered.")
            return True

        except TelegramError as exc:
            if attempt < TELEGRAM_RETRY_MAX:
                logger.warning(
                    "Telegram error on attempt %d: %s. Retrying in %ds...",
                    attempt, exc, TELEGRAM_RETRY_DELAY,
                )
                await asyncio.sleep(TELEGRAM_RETRY_DELAY)
            else:
                logger.error("Telegram delivery failed after %d attempts: %s", TELEGRAM_RETRY_MAX, exc)
                return False

        except Exception as exc:
            logger.error("Unexpected error sending Telegram message: %s", exc)
            return False

    return False


async def _test_connection_async() -> bool:
    """Send a probe message to verify the bot token and chat ID are valid.

    Returns:
        ``True`` if the test message was delivered, ``False`` otherwise.
    """
    from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False

    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        logger.info("Testing Telegram connection...")
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="Bot connected successfully.",
        )
        logger.info("Telegram connection test passed.")
        return True

    except TelegramError as exc:
        logger.error("Telegram connection test failed: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error during connection test: %s", exc)
        return False


def send_message(text: str) -> bool:
    """Synchronous wrapper for :func:`_send_async`.

    Args:
        text: MarkdownV2-formatted message body.

    Returns:
        ``True`` on delivery, ``False`` on failure.
    """
    try:
        return asyncio.run(_send_async(text))
    except Exception as exc:
        logger.error("Error in send_message: %s", exc)
        return False


def test_connection() -> bool:
    """Synchronous wrapper for :func:`_test_connection_async`.

    Returns:
        ``True`` if the bot can reach Telegram, ``False`` otherwise.
    """
    try:
        return asyncio.run(_test_connection_async())
    except Exception as exc:
        logger.error("Error in test_connection: %s", exc)
        return False
