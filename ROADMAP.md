# Project Roadmap

## Phase 1: Foundation (Completed)
*   [x] Establish basic Twitter API connection.
*   [x] Implement polling loop for a specific user.
*   [x] Curate a static list of clean jokes.
*   [x] Implement dry-run testing mode.

## Phase 2: Dynamic Content & Smarter Polling (Completed)
*   [x] Integrate external joke API or LLM for dynamic responses.
*   [x] Move away from static user IDs to dynamic configuration.
*   [x] Implement sentiment evaluation filtering to skip tragic or sensitive tweets.
*   [x] Visual Meme Card Generation with Pillow (`meme_generator.py`).
*   [ ] Implement Webhooks/Streaming API instead of polling (if API tier allows).

## Phase 3: Analytics & Unified Dashboard (Completed)
*   [x] Track engagement (likes/retweets) on bot replies in SQLite.
*   [x] Consolidated single-page command center to monitor bot status, logs, and success rates.
*   [x] Add interactive testing sandboxes and runtime target configuration to web dashboard.
*   [x] Provide a cross-platform desktop system tray companion (`tray.py`).
*   [x] Dynamic Theme Engine with Dark/Light mode switcher and persistent API state.
*   [x] Multi-Persona Humor Profiles (`tactful_engineer`, `witty_ai`, `deadpan_astronomer`) with tailored prompts.
*   [x] Community Joke Rating & Review System (+1/-1 votes, approval rate metric card, `/api/ratings`).
*   [x] Scheduled Tweet Queuing System (`scheduler.py`, `scheduled_tweets` schema, `/api/schedule`, and queue management UI).
*   [x] Weekly Visual Calendar Planner & Queue Metrics Breakdown (`/api/schedule` weekly distribution and 7-day visual planner grid).

## Phase 4: Autonomous Operations & Multi-Platform Syndication (In Progress)
*   [x] Automated weekly performance digest engine and exportable markdown report (`digest.py`, `/api/digest`).
*   [x] Automated digest external webhook dispatch engine (`webhook.py`, `/api/webhook`, Discord/Slack/Generic adapters).
*   [x] Automated recurring background worker for periodic digest webhook broadcast (`check_and_dispatch_recurring_digest`).
*   [x] Dedicated CLI digest generator (`generate_digest.py`) and direct attachment download endpoints (`/api/digest/download`).
*   [x] Multi-window performance delta trends and operational health scorecard (`digest.py`, dashboard banner).
*   [x] Bluesky & Mastodon social federation syndication engine (`syndication.py`, `/api/syndication`, dashboard federation card).
*   [x] Cross-platform federation engagement polling (Mastodon favorites/reblogs & Bluesky likes/reposts metrics, `/api/syndication/poll`).
*   [x] Automated Performance Digest HTML Export & Anomaly Threshold Alerts (`digest.py`, `/api/digest/download?format=html`, webhook alert banners).
*   [x] Refined Multi-Format Digest CLI Generator & Resilient Download Stream Delivery (`generate_digest.py`, `dashboard.py`).
*   [x] Enriched Performance Digest Extraction, Top-Reply Isolation, and Embedded Anomaly Banners (`digest.py`, `webhook.py`, `templates/index.html`).
*   [x] Configurable CLI Digest Pipeline & Per-Platform Federation Metrics Breakdown (`generate_digest.py`, `digest.py`, `dashboard.py`).
*   [x] Automated Long-Form Content Splitting & Multi-Platform Syndication Chunking (`splitter.py`, `syndication.py`, `/api/split-preview`, Command Center Thread Preview UI).
*   [x] Peak Hour Auto-Scheduler & Target Window Recommendation Engine (`scheduler.py`, `/api/schedule/optimal-slot`, Command Center Peak Slot Planner).
*   [x] Cryptographic HMAC-SHA256 Webhook Payload Signing & Header Verification (`webhook.py`, `dashboard.py`, `templates/index.html`).
*   [x] Target Audience Segmentation & Dynamic Persona Routing (`db.py`, `bot.py`, `dashboard.py`, `templates/index.html`).
*   [x] Themed Visual Meme Card Styles & Binary Download Exports (`meme_generator.py`, `/api/meme/download`, Command Center theme controls).
*   [x] Multi-account Twitter / X scheduling and cross-account coordination (`db.py`, `scheduler.py`, `/api/schedule`, Command Center UI).
*   [x] Performance Digest Multi-Account Queue Breakdown & Federation Health Details (`digest.py`, `generate_digest.py`, Command Center UI).
*   [ ] Multi-image meme card attachments support in scheduled tweets.
