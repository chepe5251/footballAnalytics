"""
Unit tests for telegram.bot and configuration.

These are pure offline tests — no Telegram API calls are made.  They verify
that the module can be imported, that config values have the expected types
and ranges, and that the .env.example template contains the required keys.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_bot_module_imports():
    """telegram.bot must be importable and expose the expected public API."""
    from telegram.bot import send_message, test_connection
    assert callable(send_message),    "send_message must be callable"
    assert callable(test_connection), "test_connection must be callable"


def test_config_loads():
    """config must be importable and TELEGRAM_MAX_LENGTH must equal 4096."""
    from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_MAX_LENGTH
    assert TELEGRAM_MAX_LENGTH == 4096, (
        f"TELEGRAM_MAX_LENGTH must be 4096, got {TELEGRAM_MAX_LENGTH}"
    )
    # Tokens are sourced from .env; allow empty strings in CI where .env is absent.
    assert isinstance(TELEGRAM_TOKEN, str),   "TELEGRAM_TOKEN must be a string"
    assert isinstance(TELEGRAM_CHAT_ID, str), "TELEGRAM_CHAT_ID must be a string"


def test_env_example_exists():
    """.env.example must exist and declare both required credential keys."""
    env_example = Path(__file__).parent.parent / ".env.example"
    assert env_example.exists(), ".env.example not found in project root"

    content = env_example.read_text()
    assert "TELEGRAM_TOKEN"   in content, ".env.example must declare TELEGRAM_TOKEN"
    assert "TELEGRAM_CHAT_ID" in content, ".env.example must declare TELEGRAM_CHAT_ID"


def test_env_file_warning():
    """If .env is missing or contains placeholder values, emit a warning (non-fatal)."""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        print("  [WARN] .env not found — copy .env.example and fill in credentials.")
        return

    content = env_file.read_text()
    if "TELEGRAM_TOKEN=123456" in content or "your_token_here" in content:
        print("  [WARN] .env still contains placeholder values.")


def test_config_numeric_bounds():
    """Numeric config constants must be within sane operational ranges."""
    from config import (
        MIN_CONFIDENCE,
        MAX_PICKS_PER_DAY,
        POISSON_WEIGHT,
        DIXON_COLES_WEIGHT,
        TELEGRAM_RETRY_MAX,
        TELEGRAM_TIMEOUT,
    )
    assert 0.0 < MIN_CONFIDENCE < 1.0, "MIN_CONFIDENCE must be in (0, 1)"
    assert MAX_PICKS_PER_DAY >= 1,     "MAX_PICKS_PER_DAY must be at least 1"
    assert abs(POISSON_WEIGHT + DIXON_COLES_WEIGHT - 1.0) < 1e-9, (
        "Ensemble weights must sum to 1.0"
    )
    assert TELEGRAM_RETRY_MAX >= 1,    "TELEGRAM_RETRY_MAX must be at least 1"
    assert TELEGRAM_TIMEOUT > 0,       "TELEGRAM_TIMEOUT must be positive"


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("TELEGRAM BOT MODULE TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_bot_module_imports,
        test_config_loads,
        test_env_example_exists,
        test_env_file_warning,
        test_config_numeric_bounds,
    ]

    try:
        for t in tests:
            t()
            print(f"  [PASS] {t.__name__}")

        print("\n[ALL BOT TESTS PASSED]")
        print("\nNext steps:")
        print("  1. cp .env.example .env")
        print("  2. Set TELEGRAM_TOKEN (from @BotFather)")
        print("  3. Set TELEGRAM_CHAT_ID (from @userinfobot)")
        print("  4. python -c \"from telegram.bot import test_connection; test_connection()\"\n")
    except AssertionError as exc:
        print(f"\n[FAILED] {exc}\n")
        sys.exit(1)
