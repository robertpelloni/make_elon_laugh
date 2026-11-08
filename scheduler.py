"""
Scheduler module for Emperor Musk Bot.
Handles background evaluation and triggering of pending scheduled tweets.
"""

import logging
from datetime import datetime, timezone
import db
import joke_generator
import meme_generator
from syndication import dispatch_syndicated_post

logger = logging.getLogger(__name__)


SUPPORTED_ACCOUNTS = ["@make_elon_laugh", "@space_astronomy"]
SUPPORTED_MEDIA_THEMES = ["dark", "cyberpunk", "solar", "clean"]
SUPPORTED_MEDIA_TYPES = ["single", "composite"]
SUPPORTED_COMPOSITE_LAYOUTS = ["auto", "grid", "side-by-side"]


def enqueue_scheduled_tweet(content, scheduled_time, persona="tactful_engineer",
                            account_handle="@make_elon_laugh", media_theme=None,
                            media_type="single", composite_layout="auto", db_path=db.DB_PATH):
    """
    Enqueues a new tweet to be posted at scheduled_time (ISO 8601 string or YYYY-MM-DD HH:MM:SS)
    attributed to a specific account profile and optional visual meme card or composite infographic.
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

    # Validate media theme if provided
    clean_media = None
    if media_theme and str(media_theme).strip().lower() not in ("none", "null", ""):
        candidate_theme = str(media_theme).strip().lower()
        if candidate_theme in SUPPORTED_MEDIA_THEMES:
            clean_media = candidate_theme
        else:
            raise ValueError(f"Invalid media_theme '{media_theme}'. Choose from: {SUPPORTED_MEDIA_THEMES}")

    # Validate media_type and composite_layout
    clean_type = "composite" if str(media_type).strip().lower() == "composite" else "single"
    clean_layout = str(composite_layout).strip().lower() if composite_layout else "auto"
    if clean_layout not in SUPPORTED_COMPOSITE_LAYOUTS:
        clean_layout = "auto"

    return db.schedule_tweet(
        content, scheduled_time, persona=persona,
        account_handle=account_handle, media_theme=clean_media,
        media_type=clean_type, composite_layout=clean_layout,
        db_path=db_path
    )


def get_pending_due_tweets(now_dt=None, db_path=db.DB_PATH):
    """
    Finds all pending scheduled tweets whose scheduled_time <= now_dt.
    Handles scheduled_time formatted as ISO string, datetime string, or integer unix timestamp.
    """
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    now_ts = now_dt.timestamp()

    pending = db.get_scheduled_tweets(status="pending", limit=50, db_path=db_path)
    due = []
    for t in pending:
        raw_st = t.get("scheduled_time")
        if isinstance(raw_st, (int, float)):
            if raw_st <= now_ts:
                due.append(t)
        elif isinstance(raw_st, str):
            if raw_st <= now_str:
                due.append(t)
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
        media_theme = tweet.get("media_theme")
        media_type = tweet.get("media_type", "single")
        composite_layout = tweet.get("composite_layout", "auto")

        media_info = ""
        if media_theme:
            if media_type == "composite":
                media_info = f" [Attached Composite Infographic: {media_theme} (layout: {composite_layout})]"
            else:
                media_info = f" [Attached Meme: {media_theme}]"

        logger.info(
            f"[{mode_label}][Account: {acc}]{media_info} "
            f"Triggering scheduled tweet ID {tweet['id']}: {tweet['content']}"
        )

        # Generate attached media binary if media_theme is configured
        if media_theme:
            try:
                if media_type == "composite":
                    img_bytes = meme_generator.create_composite_infographic(
                        panels=None,
                        theme=media_theme,
                        layout=composite_layout or "auto",
                        title=f"{acc} Autonomous Briefing",
                        subtitle=f"Scheduled Broadcast | {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                    )
                    logger.info(
                        f"Generated {len(img_bytes)} bytes composite infographic "
                        f"({media_theme}, {composite_layout}) for tweet ID {tweet['id']}."
                    )
                else:
                    card_bytes = meme_generator.create_meme_card(tweet["content"], theme=media_theme)
                    logger.info(
                        f"Generated {len(card_bytes)} bytes meme card image "
                        f"({media_theme}) for tweet ID {tweet['id']}."
                    )
            except Exception as meme_err:
                logger.warning(f"Failed to generate media for scheduled tweet {tweet['id']}: {meme_err}")

        # In a real environment, this sends through Tweepy or mocks it
        db.update_scheduled_tweet_status(tweet["id"], "sent", db_path=db_path)

        # Trigger syndication to federated platforms resolved per account profile
        try:
            from syndication import resolve_platforms_for_account
            target_platforms = resolve_platforms_for_account(acc, fallback_to_defaults=True, db_path=db_path)
            if target_platforms:
                dispatch_syndicated_post(tweet["content"], platforms=target_platforms, dry_run=dry_run)
            else:
                logger.info(f"Syndication bypassed for account {acc} (no active routing rules).")
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
