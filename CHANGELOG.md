# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.35.0] - 2026-11-08

### Added
- **Dynamic Multi-Platform Syndication Metrics & Windowed Federation Engagement Deltas (`db.py`, `digest.py`)**:
  - Enhanced `db.get_syndication_summary_metrics(days, start_days_ago, db_path)` to dynamically discover arbitrary federation platforms (Mastodon, Bluesky, Nostr, etc.) from `syndicated_posts` records rather than relying on hardcoded platform keys.
  - Added optional window filtering with relative offset boundaries (`start_days_ago` and `days`) enabling rolling window comparisons.
  - Updated `digest.generate_performance_digest()` to compute multi-window deltas for `syndication_posts` and `syndication_engagement` (total likes + shares across all federated platforms) comparing the current window against the preceding window of identical duration.
  - Refactored `digest.export_digest_markdown()` and `digest.export_digest_html()` to dynamically iterate and render engagement summaries and average engagement rates for any discovered platform with zero-division protection.
  - Enhanced Command Center UI in `templates/index.html` to display live federated post deltas (`#syndication-delta-display`).
  - Added unit test `test_syndication_window_metrics_and_deltas` in `test_bot.py` validating dynamic platform discovery, window filtering, and delta computations (108 passing unit tests, 0 `flake8` warnings).

## [0.34.0] - 2026-11-08

### Added
- **Visual Meme Card Attachments in Scheduled Tweet Queue**:
  - Enhanced database schema in `db.py` with `media_theme` column on `scheduled_tweets` and automatic migration handling.
  - Updated `schedule_tweet()` and `get_scheduled_tweets()` to persist and return media theme selections (`dark`, `cyberpunk`, `solar`, `clean`).
  - Updated `scheduler.py` to validate `media_theme` against supported palettes and dynamically generate styled Pillow infographic cards via `meme_generator.create_meme_card()` upon dispatch.
  - Updated `/api/schedule` in `dashboard.py` to accept and serialize `media_theme` metadata.
  - Added `Media Card` selector dropdown and styled queue table badges in `templates/index.html`.
  - Added comprehensive unit test `test_schedule_with_media_theme` in `test_bot.py`.

## [0.33.0] - 2026-11-08

### Added
- **Automated Queue Rephrasing & Dynamic Tone Variation (`joke_generator.py`)**:
  - Implemented `TONE_STYLES` dictionary (`witty`, `concise`, `enthusiastic`, `academic`) with prompt instructions and stylistic prefixes/suffixes.
  - Implemented `rephrase_content(content, persona, tone_style)` with OpenAI prompt tuning and resilient offline heuristic fallbacks.
- **Content Rephrasing REST API (`dashboard.py`)**:
  - Added `/api/content/rephrase` POST endpoint returning rephrased content, character count, and tone metadata with input validation.
- **Command Center Dynamic Tone Stylist & Rephraser (`templates/index.html`)**:
  - Added Tone Stylist tool strip featuring style selector, rephrase trigger, and one-click copy to the Scheduled Tweet Queue.
  - Added tooltip markers explaining tone effects and audience alignment.
- **Automated Unit Tests & Visual Verification**:
  - Added test suite in `test_bot.py` verifying rephrasing across all styles, boundaries, and `/api/content/rephrase` (106 tests passing, flake8 clean).
  - Verified UI rendering via Playwright screenshot.

## [0.32.0] - 2026-11-08

### Added
- **Performance Digest Multi-Account Queue Breakdown & Federation Health Details (`digest.py`, `generate_digest.py`)**:
  - Enhanced performance digest engine (`digest.py`) with `account_distribution` aggregation within scheduled queue metrics.
  - Updated Markdown and HTML digest report generators with visual badge styling and account attribution breakdown.
  - Extended CLI tool (`generate_digest.py`) with `--account` argument for filtering queue attribution metrics by specific handle.
  - Updated REST API endpoint `/api/digest` in `dashboard.py` to support optional `account` filtering.
  - Added dedicated dynamic UI element (`#digest-queue-accounts`) in Command Center Weekly Performance Digest card to display live account attribution distributions.
  - Verified with 105 automated unit tests, strict flake8 linting, and Playwright visual screenshot verification.

## [0.31.0] - 2026-11-08

### Added
- **Multi-Account Scheduled Tweet Routing & Account Profiles (`db.py`, `scheduler.py`)**:
  - Extended `scheduled_tweets` SQLite schema and automated migration logic with `account_handle` column (defaulting to primary `@make_elon_laugh`).
  - Updated `db.schedule_tweet` and `db.get_scheduled_tweets` to persist and filter by `account_handle`.
  - Enhanced `scheduler.enqueue_scheduled_tweet` with account normalization and `scheduler.process_due_tweets` with account attribution logging.
- **Multi-Account Schedule REST APIs (`dashboard.py`)**:
  - Enhanced `/api/schedule` (GET & POST) to handle optional `account_handle` queries and submissions.
  - Returns `account_counts` distribution alongside existing calendar breakdown.
- **Command Center Multi-Account Queue Controls (`templates/index.html`)**:
  - Added Account Profile selector dropdown (`@make_elon_laugh [Primary]`, `@space_astronomy [Secondary]`) with tooltip guidance.
  - Added dedicated Account column and visual badge indicator in the Scheduled Tweet Queue table.
- **Comprehensive Unit Testing Suite**:
  - Added tests in `test_bot.py` covering multi-account persistence, handle filtering, and `/api/schedule` REST endpoints (105 passing tests, 0 `flake8` warnings).

## [0.30.0] - 2026-11-07

### Added
- **Multi-Theme Visual Meme Card Engine (`meme_generator.py`, `joke_generator.py`)**:
  - Added `THEME_PALETTES` dictionary defining distinct visual palettes: Cosmic Slate (`dark`), Neon Cyberpunk (`cyberpunk`), Solar Flare (`solar`), and Minimalist Light (`clean`).
  - Extended `create_meme_card(text, title, theme, subtitle)` to render theme-specific backgrounds, cards, primary/secondary borders, titles, text, and accent colors.
  - Updated `joke_generator.py`'s `generate_meme_card_b64` to forward `theme` parameters cleanly.
- **Meme Theme Generation & Binary Download REST Endpoints (`dashboard.py`)**:
  - Enhanced `/api/test-generate-meme` to accept `theme` parameter and return theme-tailored base64 image cards.
  - Implemented `/api/meme/download` streaming binary PNG files as downloadable attachments (`meme_card_<theme>_<timestamp>.png`).
- **Command Center Visual Meme Card UI Controls (`templates/index.html`)**:
  - Added theme selection dropdown (Cosmic Slate, Neon Cyberpunk, Solar Flare, Minimalist Light) directly next to the Meme Card button.
  - Added a dedicated "Download PNG Card" action button beneath the rendered meme card preview.
  - Added explanatory tooltips guiding theme choices and one-click graphic downloads.
- **Comprehensive Unit Testing**:
  - Added unit tests in `test_bot.py` covering theme palettes, invalid fallback handling, base64 generation across themes, and binary `/api/meme/download` responses (expanded to 105 passing tests with 0 `flake8` warnings).

## [0.29.0] - 2026-11-07

### Added
- **Target Audience Segmentation & Persona Routing Engine (`db.py`, `bot.py`)**:
  - Implemented `target_profiles` database table schema and CRUD helpers (`get_target_profiles`, `upsert_target_profile`, `delete_target_profile`, `get_target_persona_override`).
  - Updated `bot.py` continuous polling loop to resolve target-specific persona overrides dynamically during tweet detection and respect per-target auto-reply switches.
- **Target Profiles REST API (`dashboard.py`)**:
  - Added `/api/targets` endpoint (GET, POST, DELETE) for retrieving, configuring, and removing target profiles and persona routes.
- **Command Center Target Routing UI (`templates/index.html`)**:
  - Integrated interactive Target Audience Segmentation & Persona Routing manager in the Command Center.
  - Added target creation form with User ID, handle, persona selector, auto-reply toggle, status badges, and tooltip guides.
- **Test Suite Expansion**:
  - Added unit test suite in `test_bot.py` covering database operations, persona resolution, and API endpoints (expanded to 104 passing tests with 0 `flake8` warnings).

## [0.28.0] - 2026-11-07

### Added
- **Cryptographic HMAC-SHA256 Webhook Payload Signing (`webhook.py`)**:
  - Implemented `compute_webhook_signature(payload_bytes, secret)` computing standard HMAC-SHA256 digests (`sha256=<hex_digest>`).
  - Updated `dispatch_webhook` and `check_and_dispatch_recurring_digest` to attach `X-Hub-Signature-256` and `X-Signature-Timestamp` headers when a secret is configured.
- **Webhook Secret Key Configuration REST API (`dashboard.py`)**:
  - Enhanced `/api/webhook` (GET & POST) to handle optional `webhook_secret` configuration.
  - Symmetrically returns masked secret status (`abc...xyz` or `***`) to protect credentials from shoulder-surfing.
- **Command Center Secret Key Controls & Visual Badges (`templates/index.html`)**:
  - Added password-masked HMAC Secret input field with detailed tooltip explanation of signature verification headers.
  - Added active signature status indicator (`🔒 Signed`) on the webhook configuration status badge.
- **Comprehensive Unit Testing**:
  - Added tests in `test_bot.py` covering signature computation, header attachment verification, secret masking, and API dispatch validation. Total test count expanded to 102 passing tests with 0 `flake8` warnings.

## [0.27.0] - 2026-11-07

### Added
- **Peak Hour Auto-Scheduler (`scheduler.py`)**:
  - Added `recommend_optimal_post_slot(now_dt, db_path)` calculating candidate peak engagement windows (09:00, 13:00, 17:00, 21:00 UTC) with audience rationale.
  - Automatically targets high-traffic space and tech industry windows and handles next-day rollovers.
- **Optimal Slot Recommendation REST API (`/api/schedule/optimal-slot`)**:
  - Added REST endpoint in `dashboard.py` returning optimal slot ISO timestamp, formatted local string, UTC hour, and industry reasoning.
- **Command Center Peak Slot Planner UI (`templates/index.html`)**:
  - Added `⚡ Suggest Peak Slot` button with detailed tooltip explanation.
  - Added dynamic `#optimal-slot-banner` alert banner populating the schedule datetime picker with the recommended timestamp and audience rationale.
- **Automated Tests**: Added `test_recommend_optimal_post_slot` in `test_bot.py` validating UTC calculations, next-day boundary conditions, and API endpoint output. Total test count reached 100 passing tests with 0 flake8 errors.

## [0.26.0] - 2026-11-07

### Added
- **Cross-Platform Thread Splitting & Chunking Engine (`splitter.py`)**:
  - Word-boundary-aware chunking algorithm splitting long-form text according to platform character limits: Twitter/X (280 chars), Bluesky (300 chars), and Mastodon (500 chars).
  - Automatically calculates and appends sequential thread indicators (`[1/N]`, `[2/N]`) preserving space within platform limits.
  - Handles single long words and arbitrary formatting without truncation or crashing.
- **Automated Long-Form Syndication Integration (`syndication.py`)**:
  - Enhanced `dispatch_syndicated_post()` with `auto_split=True` support.
  - Automatically splits oversized text into sequenced thread parts across Mastodon and Bluesky, publishing each part and persisting engagement records in SQLite (`syndicated_posts`).
- **Thread Split Simulation & Preview REST API (`/api/split-preview`)**:
  - Added REST endpoint in `dashboard.py` accepting arbitrary content and returning simulated thread chunk lists and character counts for Twitter, Bluesky, and Mastodon.
- **Command Center Thread Split Interactive UI (`templates/index.html`)**:
  - Added dedicated `🧵 Thread Split Preview` action button with tooltip marker in the Content Generation Sandbox.
  - Interactive multi-column preview container rendering sequenced chunks and character count badges for all three supported platforms.
- **Automated Testing Suite (`test_bot.py`)**:
  - Added comprehensive unit test `test_content_splitter_and_syndication_chunking` verifying boundary preservation, sequential indexing, dry-run syndication auto-chunking, and `/api/split-preview` responses. Total test count reached 98 passing tests with 0 flake8 errors.

## [0.24.0] - 2026-11-07

### Added
- **Configurable CLI Digest Pipeline (`generate_digest.py`)**: Added `--prefix` custom filename prefixing, `--quiet` mode for silent automation, `--json-indent` spacing control, and structured `main(cli_args)` entry point with integer process exit codes (0 for success, 1 on failure).
- **Per-Platform Federation Engagement Rates**: Enhanced `export_digest_markdown()` and `export_digest_html()` in `digest.py` to calculate and render average engagement per post across Mastodon ActivityPub and Bluesky ATProto.
- **Bounded Dashboard Report Download Endpoint**: Enhanced `/api/digest/download` in `dashboard.py` with sanitization and bounding for `days` (1-365) and custom filename prefix parameters.
- **Automated Tests**: Added `test_cli_digest_generator_and_custom_options` in `test_bot.py` covering multi-format file exports, custom prefixes, stdout streaming, and download parameters. Total passing unit tests increased to 97.

## [0.23.0] - 2026-11-07

### Added
- **Top-Performing Reply Extraction & Highlighting (`digest.py`, `webhook.py`, `templates/index.html`)**:
  - Automatically queries and isolates the highest-engagement reply `(likes + retweets)` within the rolling digest window.
  - Formats top reply details (Tweet ID, likes, retweets, timestamp) into Markdown, styled HTML callout cards, and webhook payloads (Slack & Discord).
  - Wires top-performing reply snippet into the Command Center Performance Digest card.
- **Embedded Anomaly Alert & Status Callout Banners (`digest.py`)**:
  - Integrates visual alert banners directly into `export_digest_html` and `export_digest_markdown`, displaying detailed alert messages for active system anomalies or green nominal badges when all thresholds pass.
  - Adds scheduled tweet queue persona distribution tags and badges directly into HTML performance reports.
- **Automated Test Coverage Expansion (`test_bot.py`)**:
  - Added unit tests asserting top reply query extraction, HTML/Markdown report formatting, and Slack/Discord webhook serialization (96 tests passing, clean flake8).

## [0.22.0] - 2026-11-07

### Added
- **Refined CLI Digest Generator (`generate_digest.py`)**: Added support for `--format html` and `--format all` options, generating comprehensive report sets (.html, .md, .json) in a single invocation.
- **Robust Download Stream Handling (`dashboard.py`)**: Strengthened `/api/digest/download` with input sanitization, non-zero day window defaults, and dual-layer exception handlers to guarantee resilient file delivery under database latency or corrupt data.
- **Automated CLI Export Testing (`test_bot.py`)**: Added test coverage verifying that `export_format='all'` accurately writes valid HTML5 doctype reports alongside Markdown and JSON files.

## [0.21.0] - 2026-11-07

### Added
- **Automated Performance Digest HTML Export (`digest.py`)**: Dedicated `export_digest_html()` function generating a responsive, standalone HTML performance report styled with modern CSS cards, status pills, and delta metrics for browser downloading or email dispatch.
- **Operational Performance Threshold Alerts (`digest.py`)**: Added `evaluate_performance_alerts()` detecting anomalies across SQLite connectivity, scheduled tweet backlogs (>50 pending posts), and low community humor approval ratings (<40% approval across >=5 ratings).
- **Threshold Alerts Integration in Webhook Payloads (`webhook.py`)**: Slack and Discord adapters now parse and highlight active system anomaly alerts directly in outgoing webhook dispatches.
- **HTML Digest Attachment REST Endpoint (`/api/digest/download`)**: Added `format=html` support to `/api/digest/download` in `dashboard.py` returning timestamped `.html` reports with `text/html` headers.
- **Command Center HTML Download Button & Active Alert Indicators (`templates/index.html`)**: Added one-click "Download .HTML" button and dynamic alert pill badge into the Weekly Performance Digest card.
- **Comprehensive Unit Testing Suite**: Added unit tests in `test_bot.py` covering HTML export syntax, threshold alert trigger conditions, and `/api/digest/download?format=html` response headers (95 unit tests passing, 88% coverage, 0 flake8 errors).

## [0.20.0] - 2026-11-07

### Added
- **Cross-Platform Federation Engagement Polling (`syndication.py`, `db.py`)**: Autonomous metrics polling engine tracking favorites/reblogs across Mastodon instances and likes/reposts across Bluesky ATProto repositories.
- **Syndicated Posts Persistence (`db.py`)**: Added `syndicated_posts` table to SQLite tracking platform post IDs, content, likes, shares, timestamps, and aggregated statistics (`get_syndication_summary_metrics`).
- **Federated Engagement Aggregations (`digest.py`)**: Integrated Mastodon reach and Bluesky reach directly into weekly digests and Markdown report exports.
- **Federation Metrics REST API (`/api/syndication/metrics`, `/api/syndication/poll`)**: Endpoints in `dashboard.py` to retrieve platform reach breakdown and trigger on-demand metrics polling cycles.
- **Command Center Federated Reach Strip (`templates/index.html`)**: Added live analytics strip inside the Social Federation Syndication card displaying Mastodon Reach, Bluesky Reach, Federated Total posts, and an interactive "Poll Metrics" action button with toast feedback.
- **Comprehensive Unit Testing**: Added unit tests in `test_bot.py` covering syndicated post tracking, engagement polling mock cycles, and dashboard API routes (93 unit tests passing, 88% coverage, 0 flake8 errors).

## [0.19.0] - 2026-11-07

### Added
- **Multi-Platform Social Federation Syndication (`syndication.py`)**: Dedicated syndication engine supporting Mastodon (ActivityPub REST v1 API) and Bluesky (ATProto repo record creation). Features retry backoff, dry-run simulation mode, and token masking.
- **Federated Content Distribution Triggers (`bot.py`, `scheduler.py`)**: Asynchronous, non-blocking hooks automatically federating content whenever a live reply is dispatched or a scheduled calendar post is executed.
- **Syndication Management API Endpoints (`dashboard.py`)**: Added `/api/syndication` GET and POST routes to view status, configure instance URLs/credentials, and trigger on-demand test broadcasts with dry-run support.
- **Command Center Federation Controls UI (`templates/index.html`)**: Added dedicated Social Federation Syndication section featuring Mastodon ActivityPub & Bluesky ATProto toggle cards, configuration inputs, security token masks, status indicators, and one-click test broadcast trigger.
- **Comprehensive Unit Testing Suite**: Added 7 comprehensive tests in `test_bot.py` (`TestSyndication`) covering payload formatting, live/mock HTTP requests, configuration updates, and dry-run broadcasts (92 tests passing, 89% overall test coverage, 0 flake8 errors).

## [0.18.0] - 2026-11-06

### Added
- **Multi-Window Delta Trend Comparison Engine (`digest.py`)**: Enhanced `generate_performance_digest()` to compute previous-period delta trends (comparing replies, accumulated likes, retweets, and queued dispatches against the preceding window of identical duration).
- **Operational Health Scorecard (`digest.py`, `templates/index.html`)**: Added automated health scoring tracking database connectivity, pending queue backlog, and community humor sentiment status.
- **Enriched Markdown Report Generator**: Updated `export_digest_markdown()` and CLI `generate_digest.py` with the System Operational Health Scorecard and multi-window delta trend lines.
- **Command Center Scorecard UI (`templates/index.html`)**: Added dynamic health banner (Overall Health, DB Connection, Backlog count, Sentiment) and inline delta trend tags (+diff, % change vs prior window) across digest metrics.
- **Comprehensive Unit Tests**: Added `TestEnrichedPerformanceDigest` in `test_bot.py` with 3 tests covering delta math, multi-period database aggregation, and sentiment status thresholds (85 unit tests passing, 0 flake8 errors).

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
