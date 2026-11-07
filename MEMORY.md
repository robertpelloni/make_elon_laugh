# Architectural Memory

## Internal Observations
- The repository transitioned from a troll concept into a tactful humor and astrophysics fact-sharing bot for X (Twitter).
- The web dashboard is served via Flask (`dashboard.py`) on port 5000 and is consolidated into a single-page Command Center (`templates/index.html`) prioritizing high-value features.
- All controls have explicit interactive forms, distinct labels, and tooltip guidance for complete operational clarity.
- Visual meme card generation is provided via `meme_generator.py` and `joke_generator.py` using Pillow, outputting base64-encoded PNG cards accessible at `/api/test-generate-meme`.
- The desktop system tray companion is located in `tray.py`, allowing operators on desktop environments to launch the dashboard, run checks, and quit servers, while cleanly detecting headless environments and remaining non-blocking.
- The global version string is governed centrally by `VERSION.md` (currently `0.22.0`) and dynamically read by the dashboard and documentation.
- Dual Dark and Light mode theme architecture is managed with CSS custom properties, client-side `localStorage`, and runtime persistence via `/api/theme`.
- Multi-persona humor engine is supported across `tactful_engineer`, `witty_ai`, and `deadpan_astronomer` with tailored system prompts, static fallbacks, and runtime control via `/api/persona`.
- Community Joke Rating System allows operators to vote thumbs up (+1) or thumbs down (-1) on generated content via `/api/ratings`, with an approval rate metric card and persistent SQLite storage.
- Scheduled Tweet Queue System is powered by `scheduler.py`, `db.py` (`scheduled_tweets`), and `/api/schedule` (GET, POST, DELETE), allowing delayed post dispatching and cancellation from the Command Center UI.
- Weekly Visual Calendar Planner and Queue Metrics Badge map upcoming scheduled post distribution across Monday–Sunday in `templates/index.html` and compute metrics via `dashboard.py`.
- Automated Weekly Performance Digest Engine (`digest.py`) computes 7-day rolling performance metrics (replies, engagement, persona distribution, and community approval) exportable to Markdown and viewable via `/api/digest` and the Command Center UI.
- Multi-Window Delta Trend Comparison Engine (`digest.py`) calculates prior-period deltas and percentage changes for replies, likes, retweets, and queue dispatches.
- Operational Health Scorecard evaluates database connectivity, queue backlog, and community sentiment thresholds in real time.
- Direct report export and file downloads are supported via CLI (`generate_digest.py` into `reports/`) and REST endpoint `/api/digest/download` in `dashboard.py` (serving Markdown `.md` and JSON `.json` attachment downloads).
- Automated Webhook Dispatch Engine (`webhook.py`) delivers structured digests to external webhooks (Discord, Slack, Generic JSON) with jittered exponential backoff, recurring broadcast worker logic (`check_and_dispatch_recurring_digest`), and test dispatch support via `/api/webhook`.
- Multi-Platform Social Federation Syndication (`syndication.py`) enables cross-posting to Mastodon (ActivityPub REST v1 API) and Bluesky (ATProto repo records) with token masking and dry-run simulation mode.
- Non-blocking syndication hooks are integrated into both live bot replies (`bot.py`) and scheduled post dispatches (`scheduler.py`).
- Cross-Platform Federation Engagement Polling (`syndication.py`, `db.py`) tracks favorites/reblogs on Mastodon and likes/reposts on Bluesky, storing metrics in SQLite (`syndicated_posts`) and exposing aggregated stats via `/api/syndication/metrics` and manual/automated poll via `/api/syndication/poll`.
- The bot polling loop in `bot.py` continuously evaluates scheduled tweet dispatches, recurring digest broadcasts, and syndication metrics polling automatically.
- Automated Performance Digest HTML Export & Threshold Alerts (`digest.py`, `dashboard.py`) generate standalone responsive HTML reports (`/api/digest/download?format=html`) and evaluate anomaly alerts across database, backlog, and humor ratings.
- Webhook adapters for Slack and Discord format and highlight active performance threshold alerts in outgoing payload blocks.
- The CLI report exporter (`generate_digest.py`) supports exporting Markdown, HTML, and JSON simultaneously using `--format all` into structured timestamped archives.
- The project maintains comprehensive test coverage with 95 unit tests (`test_bot.py`) and passes all `flake8` lint checks cleanly.
