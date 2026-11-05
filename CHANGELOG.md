# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
