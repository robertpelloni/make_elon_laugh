# Project Roadmap

## Phase 1: Foundation (Current)
*   Establish basic Twitter API connection.
*   Implement polling loop for a specific user.
*   Curate a static list of clean jokes.
*   Implement dry-run testing mode.

## Phase 2: Dynamic Content & Smarter Polling
*   Integrate an external joke API or LLM to generate dynamic, contextual responses.
*   Move away from static user IDs to dynamic configuration.
*   Implement Webhooks/Streaming API instead of polling (if API tier allows) to reduce credit consumption.

## Phase 3: Analytics & Dashboard
*   Track engagement (likes/retweets) on bot replies.
*   Build a simple local web UI or dashboard to monitor bot status, logs, and success rates.
*   Implement a database to store reply history permanently (replacing the volatile in-memory set).
