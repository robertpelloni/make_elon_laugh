# Immediate Tasks (TODO)

- [x] Consolidate dashboard UI into an intuitive single-page layout.
- [x] Wire all backend controls to the UI (sandbox test generation, runtime target updating, live logs, graceful shutdown).
- [x] Add informative tooltip markers to every major UI metric and control.
- [x] Implement desktop system tray icon runner (`tray.py`) with server management and dashboard launcher.
- [x] Implement visual meme/infographic card generation (`meme_generator.py`) and UI preview.
- [x] Add automated test coverage and verification for dashboard endpoints, meme generator, and system tray.
- [x] Verify visual rendering using Playwright end-to-end testing.
- [x] Add dark/light UI theme switcher in dashboard settings with persistence and API support.
- [x] Add multi-persona humor profiles (`tactful_engineer`, `witty_ai`, `deadpan_astronomer`) with live selector in dashboard.
- [x] Add community joke rating and approval tracking system (+1/-1 votes, approval rate metric card, `/api/ratings`).
- [x] Implement autonomous scheduled tweet queue (`scheduler.py`, `scheduled_tweets` table, `/api/schedule`, and queue management UI).
- [x] Add weekly calendar visual view and queue metrics breakdown for scheduled tweets (`/api/schedule`, `#calendar-grid`, `#queue-metrics-badge`).
- [x] Implement automated weekly performance digest engine and exportable markdown report (`digest.py`, `/api/digest`, and Command Center digest card).
- [x] Implement automated digest webhook dispatcher supporting Discord, Slack, and generic JSON endpoints (`webhook.py`, `/api/webhook`, and UI alert triggers).
- [x] Extract and document historical Tweepy script draft and foundational concepts from commit history into `docs/HISTORICAL_EXTRACTS.md`.
- [x] Implement automated recurring background digest webhook worker (`check_and_dispatch_recurring_digest`) in polling loop and dashboard controls.

# Future Explorations
- [ ] Explore Enterprise X webhook endpoints for event-driven tweet triggers.
- [ ] Multi-image meme card attachments support in scheduled tweets.
- [ ] Multi-platform syndication connectors (Bluesky, Mastodon).
