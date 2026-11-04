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
