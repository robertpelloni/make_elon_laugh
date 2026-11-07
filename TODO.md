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
- [x] Implement dedicated CLI report generator (`generate_digest.py`) and direct attachment download endpoint (`/api/digest/download`).
- [x] Implement multi-window delta trend comparisons and operational health scorecard in `digest.py` and Command Center UI.
- [x] Implement multi-platform federation syndication engine (`syndication.py`, Mastodon ActivityPub & Bluesky ATProto).
- [x] Add social federation management UI, live status badges, and test broadcast trigger in Command Center UI.
- [x] Implement cross-platform federation engagement polling for Mastodon & Bluesky (`syndication.py`, `db.py`, `/api/syndication/poll`, `/api/syndication/metrics`, and UI reach stats).
- [x] Implement automated performance digest standalone HTML export with styled cards and badges (`digest.py`, `/api/digest/download?format=html`, Command Center button).
- [x] Implement automated performance threshold alerts evaluating system anomalies across database, queue backlog, and humor ratings (`digest.py`, `webhook.py`, UI badge).
- [x] Refine CLI digest generator (`generate_digest.py`) to support `--format html` and `--format all` outputs.
- [x] Implement defensive error resilience and validation in dashboard digest attachment delivery (`/api/digest/download`).

# Future Explorations
- [ ] Explore Enterprise X webhook endpoints for event-driven tweet triggers.
- [ ] Multi-image meme card attachments support in scheduled tweets.
- [ ] Automated thread splitting for long-form cross-platform posts exceeding 280/300 characters.
