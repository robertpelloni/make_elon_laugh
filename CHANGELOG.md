# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-11-04

### Added
- **Unified Single-Page Command Center Dashboard**: Redesigned `templates/index.html` into a streamlined, high-value single-page control center prioritizing key metrics (replies, likes, retweets, health).
- **Interactive Content Generation & Sentiment Sandbox**: Live form and `/api/test-generate` endpoint to test jokes, astrophysics facts, and sentiment analysis ('SKIP' on sensitive context) directly from the UI.
- **Dynamic Configuration Management**: `/api/config` GET/POST endpoint and UI controls to inspect and update monitored target user IDs during runtime.
- **Live Diagnostics Log Streamer**: In-memory ring buffer log handler (`InMemoryLogHandler`) and `/api/logs` endpoint streaming real-time operational messages to an integrated terminal in the dashboard.
- **On-Demand Cycle Simulation**: `/api/run-check` endpoint enabling immediate dry-run simulations and state persistence testing from both dashboard and companion utilities.
- **Graceful Server Shutdown**: `/api/shutdown` endpoint to cleanly terminate backend and web services on operator demand.
- **Desktop System Tray Companion (`tray.py`)**: Optional desktop system tray runner with menu options to open the dashboard, trigger checks, and quit servers gracefully, with auto-fallback for headless/Docker environments.
- Comprehensive unit test coverage for new endpoints and system tray companions in `test_bot.py`.

## [0.6.0] - 2026-07-18

### Added
- "Fact of the Day" functionality alternating between jokes and astrophysics facts.
- Sentiment analysis filtering in LLM content generation to prevent inappropriate replies.

## [0.5.0] - 2026-07-18

### Added
- Initial dynamic OpenAI joke generation fallback.
- SQLite database persistence with engagement metrics polling.
- Local Flask monitoring dashboard.
- Rate limiter with exponential backoff and jitter.
- Dockerfile, start scripts, and CI/CD GitHub Actions workflow.
