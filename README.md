# Emperor Musk Bot (`make_elon_laugh`)

A playful Twitter (X) humor bot that replies to Elon Musk and space/engineering topics with lighthearted jokes, astrophysics facts, and visual meme cards. Built with Python, Tweepy (async), OpenAI API, Pillow, Flask, and SQLite.

## Status

**Active hobby project (v0.38.0).** Last significant activity: **2026-11-12** — merge of a Jules feature branch (Protocol #281). v0.38.0 ("Digest & Queue Visibility Refinement") was released repeatedly Nov 9–11, 2026.

Whether the bot is currently running against a live X account is not stated anywhere in the repo — the code supports it, but there is no deployment record here.

## What it does

- **Command Center dashboard** (`http://localhost:5000`) — single-page monitoring UI with engagement metrics, live diagnostics logs, and system health
- **Multi-persona content engine** — `Tactful Rocket Scientist`, `Witty Cybernetic AI`, or `Deadpan Deep-Space Observer`, with curated fallback humor
- **Sentiment & content sandbox** — test joke/fact generation in the browser; sentiment analysis skips serious or tragic tweets
- **Meme/infographic card generator** — Pillow-based graphic cards for tweets or dashboard preview (`meme_generator.py`)
- **Dynamic account tracking** — monitor multiple user IDs, adjustable through the UI
- **State persistence & analytics** — replied-tweet history and cumulative likes/retweets in SQLite
- **Safety & rate limiting** — exponential backoff with jitter against HTTP 429s
- **System tray companion** (`tray.py`) — desktop runner: status, dashboard launch, dry-run checks, graceful shutdown
- **Docker + GitHub Actions CI** — containerized, automated testing

## Layout

- `bot.py` — polling loop and reply logic; `dashboard.py` — Flask command center; `db.py` — SQLite persistence
- `joke_generator.py`, `meme_generator.py`, `digest.py`, `generate_digest.py` — content engines
- `scheduler.py`, `rate_limiter.py`, `auth.py`, `analytics.py`, `splitter.py`, `syndication.py`, `webhook.py`, `tray.py`
- `test_bot.py` — unittest suite; `templates/` — dashboard UI; `docs/`, `reports/` — docs and generated reports

## Quick start

```bash
git clone https://github.com/robertpelloni/make_elon_laugh.git
cd make_elon_laugh
pip install -r requirements.txt
cp .env.example .env   # fill in X API + OpenAI credentials
./start.sh
```

Open http://localhost:5000 for the dashboard. Dry-run mode (no Twitter API writes):

```bash
python bot.py --dry-run
```

Tests: `python -m unittest test_bot.py`. Lint: `flake8 .`
