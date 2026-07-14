# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - Resilience and CI/CD Release
### Added
- **Data Validation Layer:** Input parser now aggressively checks types, scrubs whitespace, and filters malformed API objects (e.g., missing IDs or text).
- **Rate Limiter:** Custom `call_api_with_backoff` module wrapping API calls with exponential backoff and randomized jitter to handle HTTP 429 errors and network latency (e.g., timeouts, dropped connections).
- **CI/CD Pipeline:** Fully operational GitHub Actions workflow (`ci.yml`) triggering on `main` that handles automated linting (`flake8`), unit testing, `--dry-run` integration checks, and continuous deployment to GitHub Container Registry (GHCR).
- **Containerization:** Extracted secrets to `.env` variables and added `Dockerfile` and `requirements.txt` for robust, environment-agnostic deployment.
- **Testing:** Comprehensive `unittest` suite covering API key boundaries, payload boundary cases, and edge-case exceptions.

## [0.1.0] - Initial Release
### Added
- `bot.py` containing the core logic for polling Twitter and posting replies.
- List of 20 clean, space/engineering/Mars-themed jokes.
- `--dry-run` flag to safely test the bot without making actual API calls.
- Staggered waiting logic (4-6 hours + random delay) to comply with API limits and anti-spam measures.
- Core governance documentation (VISION.md, ROADMAP.md, TODO.md, MEMORY.md, DEPLOY.md, IDEAS.md).
