# Emperor Musk Bot (`make_elon_laugh`)

[![CI/CD Pipeline](https://github.com/robertpelloni/make_elon_laugh/actions/workflows/ci.yml/badge.svg)](https://github.com/robertpelloni/make_elon_laugh/actions)

A playful, tactful Twitter (X) autonomous humor bot designed to engage with Elon Musk and space/engineering topics with lighthearted, clean jokes and fascinating astrophysics facts.

Built with Python, Tweepy (async), OpenAI API, Flask, and SQLite.

---

## Features

- **Consolidated Command Center**: A unified single-page monitoring dashboard (`http://localhost:5000`) showing real-time engagement metrics, live diagnostics logs, and system health status.
- **Interactive Sentiment & Content Sandbox**: Test joke and astrophysics fact generation right from the browser. Supports OpenAI dynamic responses with sentiment analysis that automatically skips serious or tragic tweets.
- **Dynamic Account Tracking**: Track multiple user IDs simultaneously and adjust monitored accounts directly through the UI.
- **State Persistence & Analytics**: Stores replied tweet history and tracks cumulative likes and retweets using SQLite.
- **Safety & Rate Limiting**: Exponential backoff with jitter protection against HTTP 429 Too Many Requests and network latency dropouts.
- **System Tray Companion (`tray.py`)**: Desktop system tray runner to view status, launch the dashboard, run dry-run checks, and gracefully shut down servers.
- **Containerized & CI/CD Automated**: Full Docker support and automated testing via GitHub Actions.

---

## Quick Start

### 1. Installation
```bash
git clone https://github.com/robertpelloni/make_elon_laugh.git
cd make_elon_laugh
pip install -r requirements.txt
```

### 2. Environment Setup
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Launching
```bash
./start.sh
```
Open [http://localhost:5000](http://localhost:5000) to view the Command Center dashboard.

To run in dry-run mode (simulating without Twitter API writes):
```bash
python bot.py --dry-run
```

---

## Testing & Code Quality

Run tests:
```bash
python -m unittest test_bot.py
```

Run linting:
```bash
flake8 .
```

Run test coverage report:
```bash
coverage run -m unittest test_bot.py && coverage report
```
