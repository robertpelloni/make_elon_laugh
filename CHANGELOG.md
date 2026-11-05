# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.14.0] - 2026-11-05

### Added
- **Automated Performance Digest Engine (`digest.py`)**: Computes 7-day rolling window analytics across bot replies, engagement (likes/retweets), queued tweets by persona and status, and community humor approval ratings.
- **Markdown Digest Exporter**: Supports exporting human-readable Markdown summaries via `export_digest_markdown()`.
- **Digest API Endpoint (`/api/digest`)**: Added endpoint in `dashboard.py` supporting `format=json` and `format=markdown` queries with custom window days.
- **Command Center Digest Card (`templates/index.html`)**: Integrated interactive 'Weekly Performance Digest & Insights' card with real-time badges and expandable Markdown export modal.
- **Unit Test Coverage**: Added tests for empty database handling, weekly aggregations, Markdown export, and `/api/digest` HTTP endpoint in `test_bot.py` (72 tests passing, 88% coverage).

## [0.13.0] - 2026-11-05

### Added
- **Weekly Visual Calendar Grid (`templates/index.html` & `dashboard.py`)**: Added a 7-day Monday–Sunday visual calendar planner strip showing pending scheduled tweet counts per day with day-of-week active indicators.
- **Queue Status Metrics Pill**: Integrated real-time pending and sent counts directly into the Scheduled Tweet Queue card header (`X Pending / Y Sent`).
- **Enhanced Schedule REST API**: `/api/schedule` GET endpoint now computes and returns `weekly_calendar` breakdown and comprehensive queue metrics (`pending`, `sent`, `cancelled`).
- **Comprehensive Unit Tests**: Added unit tests in `test_bot.py` verifying `/api/schedule` returns `weekly_calendar` and queue metrics accurately.
- **Playwright Frontend Visual Verification**: Captured full-page visual rendering confirming 7-day calendar planner layout and dynamic queue updates.

## [0.12.0] - 2026-11-05

### Added
- **Scheduled Tweet Queuing System (`scheduler.py`)**: Built an autonomous queue system supporting enqueuing tweets with custom personas, finding pending due tweets, and batch-dispatching them.
- **Database Schema for Scheduled Tweets (`db.py`)**: Added `scheduled_tweets` table with automatic migration and functions (`schedule_tweet`, `get_scheduled_tweets`, `update_scheduled_tweet_status`).
- **Schedule Management REST API (`/api/schedule`)**: Added endpoints in `dashboard.py` supporting GET (retrieving queue and historical items), POST (enqueuing new timed tweets with datetime and persona validation), and DELETE (cancelling pending items).
- **Command Center Scheduled Tweet UI (`templates/index.html`)**: Added an interactive "Scheduled Tweet Queue" section featuring datetime picker, persona selection, quick queue preview, status badges, and one-click cancellation.
- **Visual & Automated Verification**: Verified with Playwright visual testing and added unit tests in `test_bot.py` (68 unit tests passing, 87% coverage, 0 flake8 errors).

## [0.11.0] - 2026-11-05

### Added
- **Data Validation Layer:** Input parser now aggressively checks types, scrubs whitespace, and filters malformed API objects (e.g., missing IDs or text).
- **Rate Limiter:** Custom `call_api_with_backoff` module wrapping API calls with exponential backoff and randomized jitter to handle HTTP 429 errors and network latency (e.g., timeouts, dropped connections).
- **CI/CD Pipeline:** Fully operational GitHub Actions workflow (`ci.yml`) triggering on `main` that handles automated linting (`flake8`), unit testing, `--dry-run` integration checks, and continuous deployment to GitHub Container Registry (GHCR).
- **Containerization:** Extracted secrets to `.env` variables and added `Dockerfile` and `requirements.txt` for robust, environment-agnostic deployment.
- **Testing:** Comprehensive `unittest` suite covering API key boundaries, payload boundary cases, and edge-case exceptions.

## [0.1.0] - Initial Release
### Added
- `bot.py` containing the core logic for polling Twitter and posting replies.
- List of 20 clean, space/engineering/Mars-themed jokes.
- `--dry-run` flag to safely test the bot without making actual API calls.
- Staggered waiting logic (4-6 hours + random delay) to comply with API limits and anti-spam measures.
- Core governance documentation (VISION.md, ROADMAP.md, TODO.md, MEMORY.md, DEPLOY.md, IDEAS.md).
