# Memory & Architectural Observations

## Internal Observations
- The repository transitioned from a troll concept into a tactful humor and astrophysics fact-sharing bot for X (Twitter).
- The web dashboard is served via Flask (`dashboard.py`) on port 5000 and is consolidated into a single-page Command Center (`templates/index.html`) prioritizing high-value features.
- All controls have explicit interactive forms, distinct labels, and tooltip guidance for complete operational clarity.
- Visual meme card generation is provided via `meme_generator.py` and `joke_generator.py` using Pillow, outputting base64-encoded PNG cards accessible at `/api/test-generate-meme`.
- The desktop system tray companion is located in `tray.py`, allowing operators on desktop environments to launch the dashboard, run checks, and quit servers, while cleanly detecting headless environments and remaining non-blocking.
- The global version string is governed centrally by `VERSION.md` (currently `0.13.0`) and dynamically read by the dashboard and documentation.
- Dual Dark and Light mode theme architecture is managed with CSS custom properties, client-side `localStorage`, and runtime persistence via `/api/theme`.
- Multi-persona humor engine is supported across `tactful_engineer`, `witty_ai`, and `deadpan_astronomer` with tailored system prompts, static fallbacks, and runtime control via `/api/persona`.
- Community Joke Rating System allows operators to vote thumbs up (+1) or thumbs down (-1) on generated content via `/api/ratings`, with an approval rate metric card and persistent SQLite storage.
- Scheduled Tweet Queue System is powered by `scheduler.py`, `db.py` (`scheduled_tweets`), and `/api/schedule` (GET, POST, DELETE), allowing delayed post dispatching and cancellation from the Command Center UI.
- Weekly Visual Calendar Planner and Queue Metrics Badge map upcoming scheduled post distribution across Monday–Sunday in `templates/index.html` and compute metrics via `dashboard.py`.
- Automated Weekly Performance Digest Engine (`digest.py`) computes 7-day rolling performance metrics (replies, engagement, persona distribution, and community approval) exportable to Markdown and viewable via `/api/digest` and the Command Center UI.
- The project maintains comprehensive test coverage with 72 unit tests (`test_bot.py`) and passes all `flake8` lint checks cleanly.
