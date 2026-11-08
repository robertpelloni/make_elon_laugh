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


SUPPORTED_ACCOUNTS = ["@make_elon_laugh", "@space_astronomy"]


def enqueue_scheduled_tweet(content, scheduled_time, persona="tactful_engineer",
                            account_handle="@make_elon_laugh", db_path=db.DB_PATH):
    """
    Enqueues a new tweet to be posted at scheduled_time (ISO 8601 string or YYYY-MM-DD HH:MM:SS)
    attributed to a specific account profile.
    """
    if not content or not str(content).strip():
        raise ValueError("Content cannot be empty.")

    # Validate persona
    if persona not in joke_generator.PERSONAS:
        persona = "tactful_engineer"

    # Validate and normalize account handle
    account_handle = str(account_handle).strip() if account_handle else "@make_elon_laugh"
    if not account_handle.startswith("@"):
        account_handle = f"@{account_handle}"

    return db.schedule_tweet(content, scheduled_time, persona=persona,
                             account_handle=account_handle, db_path=db_path)


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
        acc = tweet.get("account_handle", "@make_elon_laugh")
        logger.info(f"[{mode_label}][Account: {acc}] Triggering scheduled tweet ID {tweet['id']}: {tweet['content']}")
        # In a real environment, this sends through Tweepy or mocks it
        db.update_scheduled_tweet_status(tweet["id"], "sent", db_path=db_path)

        # Trigger syndication to federated platforms if enabled
        try:
            dispatch_syndicated_post(tweet["content"], dry_run=dry_run)
        except Exception as e:
            logger.warning(f"Federated syndication failed for scheduled tweet {tweet['id']}: {e}")

        processed_count += 1

    return processed_count


def recommend_optimal_post_slot(now_dt=None, db_path=db.DB_PATH):
    """
    Recommends an optimal post scheduling slot based on audience activity patterns
    and high-engagement space & tech industry windows (e.g., 09:00, 13:00, 17:00 UTC).
    Returns a dict with 'slot_iso', 'slot_formatted', 'hour_utc', and 'reasoning'.
    """
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    # Candidate high-traffic UTC engagement hours for tech/space audiences
    peak_hours = [9, 13, 17, 21]

    # Find the next peak hour today, or the first peak hour tomorrow if today's have passed
    target_date = now_dt.date()
    target_hour = None

    for h in peak_hours:
        candidate_dt = datetime(
            target_date.year, target_date.month, target_date.day, h, 0, 0, tzinfo=timezone.utc
        )
        if candidate_dt > now_dt:
            target_hour = h
            break

    if target_hour is None:
        # Move to first slot of tomorrow
        from datetime import timedelta
        target_date = target_date + timedelta(days=1)
        target_hour = peak_hours[0]

    optimal_dt = datetime(
        target_date.year, target_date.month, target_date.day, target_hour, 0, 0, tzinfo=timezone.utc
    )

    reasonings = {
        9: "Morning orbital telemetry & European tech commute peak (09:00 UTC)",
        13: "US East Coast morning wake-up & European afternoon peak (13:00 UTC)",
        17: "US West Coast tech morning & US East Coast lunch engagement peak (17:00 UTC)",
        21: "US evening prime-time launch & astrophysics discussion peak (21:00 UTC)"
    }

    reasoning = reasonings.get(
        target_hour, "Optimized engagement window for space science & tech audiences."
    )

    return {
        "slot_iso": optimal_dt.strftime("%Y-%m-%dT%H:%M"),
        "slot_formatted": optimal_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "hour_utc": target_hour,
        "reasoning": reasoning
    }
