"""
Scheduler module for Emperor Musk Bot.
Handles background evaluation and triggering of pending scheduled tweets.
"""

import logging
from datetime import datetime, timezone
import db
import joke_generator
from syndication import dispatch_syndicated_post

logger = logging.getLogger(__name__)


def enqueue_scheduled_tweet(content, scheduled_time, persona="tactful_engineer", db_path=db.DB_PATH):
    """
    Enqueues a new tweet to be posted at scheduled_time (ISO 8601 string or YYYY-MM-DD HH:MM:SS).
    """
    if not content or not str(content).strip():
        raise ValueError("Content cannot be empty.")

    # Validate persona
    if persona not in joke_generator.PERSONAS:
        persona = "tactful_engineer"

    return db.schedule_tweet(content, scheduled_time, persona=persona, db_path=db_path)


def get_pending_due_tweets(now_dt=None, db_path=db.DB_PATH):
    """
    Finds all pending scheduled tweets whose scheduled_time <= now_dt.
    """
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    pending = db.get_scheduled_tweets(status="pending", limit=50, db_path=db_path)
    due = [t for t in pending if t["scheduled_time"] <= now_str]
    return due


def process_due_tweets(dry_run=True, db_path=db.DB_PATH):
    """
    Processes all due scheduled tweets. In dry-run mode, marks them sent without API calls.
    """
    due_tweets = get_pending_due_tweets(db_path=db_path)
    processed_count = 0

    for tweet in due_tweets:
        mode_label = "DRY-RUN" if dry_run else "LIVE"
        logger.info(f"[{mode_label}] Triggering scheduled tweet ID {tweet['id']}: {tweet['content']}")
        # In a real environment, this sends through Tweepy or mocks it
        db.update_scheduled_tweet_status(tweet["id"], "sent", db_path=db_path)

        # Trigger syndication to federated platforms if enabled
        try:
            dispatch_syndicated_post(tweet["content"], dry_run=dry_run)
        except Exception as e:
            logger.warning(f"Federated syndication failed for scheduled tweet {tweet['id']}: {e}")

        processed_count += 1

    return processed_count
