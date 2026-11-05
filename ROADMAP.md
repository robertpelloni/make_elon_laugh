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

## Phase 4: Autonomous Operations & Multi-Platform Syndication (Upcoming)
*   [x] Automated weekly performance digest engine and exportable markdown report (`digest.py`, `/api/digest`).
*   [x] Automated digest external webhook dispatch engine (`webhook.py`, `/api/webhook`, Discord/Slack/Generic adapters).
*   [ ] Multi-account Twitter / X scheduling and cross-account coordination.
*   [ ] Bluesky & Mastodon social federation syndication engine.
*   [ ] Automated recurring cron worker for weekly digest webhook broadcast.
