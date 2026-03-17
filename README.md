# Soccer Picks

Automated football match prediction system that sends daily picks to Telegram.

Analyses fixtures from the top European leagues, runs a Poisson + Dixon-Coles ensemble model, and delivers confidence-gated picks every morning at 5:00 AM.

---

## Features

- Automated daily fixture analysis — Premier League, La Liga, Bundesliga, Serie A, Ligue 1
- Ensemble model: Double-Poisson (40%) + Dixon-Coles 1997 (60%)
- Confidence threshold (default ≥ 60%) — only high-signal picks are sent
- Telegram delivery with MarkdownV2 formatting
- Cross-platform: Windows, macOS, Linux
- Robust error handling with intelligent fallbacks

---

## Requirements

- Python 3.10+
- A Telegram bot token — create one with [@BotFather](https://t.me/BotFather)
- Your Telegram chat ID — get it from [@userinfobot](https://t.me/userinfobot)

---

## Installation

```bash
git clone https://github.com/chepe5251/footballAnalytics.git
cd soccer_picks

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your TELEGRAM_TOKEN and TELEGRAM_CHAT_ID
```

Verify the bot connection:

```bash
python -c "from telegram.bot import test_connection; test_connection()"
```

Run manually:

```bash
python main.py
```

---

## Configuration

All tunable parameters are in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SEND_TIME` | `"05:00"` | Daily send time (24-hour) |
| `LEAGUES` | 5 major leagues | Leagues to analyse |
| `MIN_CONFIDENCE` | `0.60` | Minimum model confidence |
| `MAX_PICKS_PER_DAY` | `5` | Cap on picks sent per day |
| `ROLLING_WINDOW` | `8` | Matches used for form stats |
| `POISSON_WEIGHT` | `0.40` | Poisson model blend weight |
| `DIXON_COLES_WEIGHT` | `0.60` | Dixon-Coles model blend weight |

Credentials go in `.env` (never commit this file):

```
TELEGRAM_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=123456789
```

---

## Automation

### Linux — systemd (recommended for servers)

```bash
bash deploy.sh          # installs venv, deps, and systemd units

sudo systemctl enable soccer-picks.timer
sudo systemctl start  soccer-picks.timer

# Monitor
sudo journalctl -u soccer-picks -f
```

### macOS — launchd

```bash
# Create ~/Library/LaunchAgents/com.soccer-picks.plist with:
# StartCalendarInterval → Hour: 5, Minute: 0
# ProgramArguments     → /path/to/venv/bin/python /path/to/main.py

launchctl load ~/Library/LaunchAgents/com.soccer-picks.plist
```

### Windows — Task Scheduler

```
Task Scheduler → Create Basic Task
Trigger: Daily at 05:00
Action:  Start a program
Program: C:\path\to\venv\Scripts\python.exe
Arguments: C:\path\to\soccer_picks\main.py
```

### All platforms — Python scheduler

```bash
python scheduler.py        # blocking loop; keep alive with your OS process manager
```

---

## Project Structure

```
soccer_picks/
├── main.py               # Pipeline entry point
├── scheduler.py          # Daily scheduler (blocking loop)
├── config.py             # All tunable parameters
├── deploy.sh             # Ubuntu/Linux server deployment
├── soccer-picks.service  # systemd service unit
├── soccer-picks.timer    # systemd timer unit (5 AM daily)
├── requirements.txt
├── .env.example
│
├── ingestion/
│   ├── calendar.py       # Fetches today's fixtures via FBref
│   └── scraper.py        # Downloads team statistics
│
├── features/
│   └── builder.py        # Builds model input features
│
├── models/
│   ├── poisson.py        # Double-Poisson model (Maher 1982)
│   └── dixon_coles.py    # Dixon-Coles model (1997)
│
├── picks/
│   ├── predictor.py      # Per-match prediction orchestrator
│   ├── filter.py         # Confidence filtering
│   └── formatter.py      # Telegram MarkdownV2 formatter
│
├── telegram/
│   └── bot.py            # Telegram Bot API client
│
├── tests/
│   ├── test_calendar.py
│   ├── test_formatter.py
│   └── test_bot.py
│
└── data/
    ├── cache/            # Temporary soccerdata cache
    └── history/          # Sent picks archive (JSON)
```

---

## Testing

```bash
python -m pytest tests/ -v
```

---

## Troubleshooting

**`ModuleNotFoundError`** — virtual environment not active:
```bash
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Telegram not sending** — check credentials:
```bash
cat .env
python -c "from telegram.bot import test_connection; test_connection()"
```

**Timer not triggering at 5 AM** — verify server timezone:
```bash
timedatectl
sudo timedatectl set-timezone America/Argentina/Buenos_Aires
sudo systemctl restart soccer-picks.timer
```

**No picks today** — normal on fixture-free days for the configured leagues.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).
