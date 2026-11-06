# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.17.0] - 2026-11-06

### Added
- **Standalone Digest CLI & File Exporter (`generate_digest.py`)**: Dedicated command-line utility to generate rolling performance digests and export them into Markdown and JSON files in `reports/` or stream directly to stdout.
- **Direct Digest Download REST Endpoint (`/api/digest/download`)**: Added endpoint in `dashboard.py` returning timestamped file attachments in Markdown (`.md`) or JSON (`.json`) formats.
- **Command Center Report Download Controls (`templates/index.html`)**: Added one-click "Download .MD" and "Download .JSON" direct action buttons into the Weekly Performance Digest card.
- **Comprehensive Unit Tests**: Added 3 unit tests in `test_bot.py` covering file saving, markdown/json download endpoints, and attachment headers (82 unit tests passing, 88% test coverage, 0 flake8 errors).

## [0.16.0] - 2026-11-06

### Added
- **Automated Recurring Digest Broadcast Worker (`webhook.py`)**: Added `check_and_dispatch_recurring_digest()` implementing background recurring broadcast intervals (e.g., 24h daily, 72h 3-day, 168h weekly) with timestamp tracking and throttling.
- **Bot Polling Loop Recurring Digest Integration (`bot.py`)**: Integrated automated digest dispatch evaluation into the primary continuous polling loop.
- **Webhook API Configuration Expansion (`dashboard.py`)**: Enhanced `/api/webhook` (GET/POST) to query and update `auto_dispatch` preference and `interval_hours` setting with runtime status reporting.
- **Command Center Recurring Controls (`templates/index.html`)**: Added intuitive Recurring Digest checkbox, interval dropdown selector, and last broadcast timestamp indicators.
- **Unit Test Coverage**: Added 3 unit tests in `test_bot.py` covering recurring digest dispatch logic (disabled, unconfigured, due dispatch, throttling) and API updates (79 unit tests passing, 88% coverage).

## [0.15.0] - 2026-11-05

### Added
- **Automated Digest Webhook Dispatcher (`webhook.py`)**: Supports automated and manual dispatch of performance digests to external webhook receivers with exponential backoff and jitter retry mechanics.
- **Platform Payload Adapters**: Built-in support for Discord (`embeds`), Slack (`blocks`), and Generic JSON payload formats.
- **Webhook Management REST API (`/api/webhook`)**: Added GET/POST endpoint in `dashboard.py` to inspect configured webhook URL (masked), update target endpoint and platform adapter, and trigger immediate test dispatches.
- **Command Center Webhook Integration UI (`templates/index.html`)**: Added intuitive Webhook Dispatch & Alerts controls within the Weekly Performance Digest card featuring status pill indicators, adapter selectors, URL inputs, and one-click test execution.
- **Unit Test Coverage**: Added 4 unit tests in `test_bot.py` covering Slack and Discord formatting adapters, mock network dispatch with retries, and `/api/webhook` REST interactions (76 unit tests passing, 88% overall test coverage).

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
- **Community Joke Rating System (`db.py`)**: Added `joke_ratings` table schema, migration logic, and helper functions (`record_joke_rating`, `get_joke_ratings`) tracking operator approval (+1/-1 votes and notes).
- **Humor Feedback REST API (`/api/ratings`)**: Added GET/POST endpoints to `dashboard.py` enabling client-side voting and retrieval of recent reviews.
- **Humor Approval Dashboard Metric & Thumbs Voting (`templates/index.html`)**: Added a 4th Hero metric card ("Humor Approval %") to the Command Center and thumbs up/down rating buttons directly on generated content preview boxes with live toast feedback.
- **Database Statistics Enhancement**: Enhanced `get_db_stats()` to aggregate total reviews and approval percentages.
- **Unit Testing**: Added unit tests in `test_bot.py` covering rating storage and API endpoints (65 unit tests passing, 88% overall test coverage, 0 flake8 errors).

## [0.10.0] - 2026-11-05

### Added
- **Multi-Persona Humor Profiles (`joke_generator.py`)**: Added selectable personality styles (`tactful_engineer`, `witty_ai`, `deadpan_astronomer`) with tailored LLM system prompts and curated static humor and astrophysics collections.
- **Persona Management REST API (`/api/persona`)**: GET/POST endpoints in `dashboard.py` allowing runtime querying and switching of active personas.
- **Interactive Persona Selector UI (`templates/index.html`)**: Added a persona dropdown, descriptive tooltips, and dynamic preview updates inside the Command Center sandbox.
- **Unit Testing**: Added test coverage in `test_bot.py` verifying persona retrieval, switching, and generation across all personas (63 unit tests passing, 0 flake8 errors).

## [0.9.0] - 2026-11-04

### Added
- **Dynamic Light/Dark Theme Switcher**: Dual-palette CSS variable design system across `templates/index.html` with instant header toggle and persistence in `localStorage`.
- **System Theme Preference API**: Added `/api/theme` (GET/POST) endpoint to `dashboard.py` to synchronize and persist user theme selections with the runtime environment.
- **Frontend Playwright Visual Verification**: Captured and verified full-page screenshot of the dashboard in Light mode.
- **Theme API Unit Testing**: Added unit tests in `test_bot.py` covering valid/invalid theme updates and retrieval (61 total unit tests passing).

## [0.8.0] - 2026-11-04

### Added
- **Visual Meme / Infographic Card Generator (`meme_generator.py`)**: Renders dark-themed 600x340 graphic cards formatted for space humor and astrophysics facts using Pillow.
- **Interactive Meme Card Sandbox (`templates/index.html`)**: Added a dedicated meme card generation button, tooltip guidance, and real-time visual image preview display.
- **Meme Generation Endpoint (`/api/test-generate-meme`)**: REST API endpoint returning base64-encoded PNG image cards for direct UI rendering or tweet image attachment pipelines.
- Unit tests in `test_bot.py` for image byte integrity and meme generator endpoint responses (60 tests passing).

## [0.7.0] - 2026-11-04

### Added
- Unified Single-Page Command Center Dashboard with categorized hero metrics.
- Interactive Content Generation & Sentiment Sandbox.
- Dynamic Configuration Management for monitored target user IDs.
- Live in-memory diagnostics log streaming.
- On-Demand Dry-Run Cycle Simulation (`/api/run-check`) and Graceful Shutdown (`/api/shutdown`).
- Desktop System Tray Companion (`tray.py`).

## [0.6.0] - 2026-07-18

### Added
- "Fact of the Day" alternating between jokes and astrophysics facts.
- Sentiment analysis filtering in LLM content generation to prevent replying to serious or tragic tweets.

## [0.5.0] - 2026-07-18

### Added
- Dynamic OpenAI joke generation fallback.
- SQLite database persistence with engagement metrics polling.
- Local Flask monitoring dashboard.
- Rate limiter with exponential backoff and jitter.
- Dockerfile, start scripts, and CI/CD GitHub Actions workflow.
