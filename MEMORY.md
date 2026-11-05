# Architectural Memory

*   **Language:** Python 3
*   **Core Library:** `tweepy` (v4, targeting API v2 endpoints).
*   **State Management:** Currently using a simple in-memory `set()` to track replied tweets. This means if the bot restarts, it forgets its history. A future architectural shift to SQLite or JSON file storage is necessary for long-term stability.
*   **Execution Model:** Continuous `while True` polling loop.
*   **Rate Limiting Strategy:** Enforced 4-6 hour sleep periods after a successful reply to avoid spam filters and reduce API credit burn.
