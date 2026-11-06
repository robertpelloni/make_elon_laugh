"""
Digest Webhook Dispatcher Module.

Formats and dispatches weekly performance digests to Discord, Slack,
or generic HTTP webhook endpoints using standard library urllib.
Includes exponential backoff retries for transient HTTP errors.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
import digest

logger = logging.getLogger(__name__)

# Global runtime configuration with fallback to environment
DEFAULT_WEBHOOK_URL = os.environ.get("DIGEST_WEBHOOK_URL", "")
DEFAULT_ADAPTER = os.environ.get("DIGEST_WEBHOOK_ADAPTER", "generic").lower()
AUTO_DISPATCH_ENABLED = os.environ.get("DIGEST_AUTO_DISPATCH", "false").lower() in ["true", "1", "yes"]
DISPATCH_INTERVAL_HOURS = int(os.environ.get("DIGEST_INTERVAL_HOURS", "168"))  # default 7 days (168 hours)
LAST_DISPATCH_TIMESTAMP = 0.0


def check_and_dispatch_recurring_digest(dry_run=False, current_time=None):
    """
    Evaluates whether the automated periodic digest is due and dispatches it.
    Returns (dispatched: bool, message: str).
    """
    global LAST_DISPATCH_TIMESTAMP

    if not AUTO_DISPATCH_ENABLED:
        return False, "Auto-dispatch disabled."

    if not DEFAULT_WEBHOOK_URL:
        return False, "No webhook URL configured."

    now = time.time() if current_time is None else current_time
    interval_seconds = max(1, DISPATCH_INTERVAL_HOURS) * 3600

    if LAST_DISPATCH_TIMESTAMP > 0 and (now - LAST_DISPATCH_TIMESTAMP) < interval_seconds:
        remaining_hours = round((interval_seconds - (now - LAST_DISPATCH_TIMESTAMP)) / 3600, 1)
        return False, f"Digest not due yet. Next dispatch in ~{remaining_hours} hours."

    logger.info("Executing scheduled recurring performance digest broadcast...")
    summary = digest.generate_performance_digest(days=7)
    payload = format_webhook_payload(summary, adapter=DEFAULT_ADAPTER)

    if dry_run:
        LAST_DISPATCH_TIMESTAMP = now
        logger.info(f"[DRY-RUN] Recurring digest simulated dispatch to {DEFAULT_ADAPTER}.")
        return True, "Simulated recurring dispatch (dry-run)."

    success, status_or_err = dispatch_webhook(DEFAULT_WEBHOOK_URL, payload)
    if success:
        LAST_DISPATCH_TIMESTAMP = now
        logger.info(f"Recurring digest successfully broadcast (HTTP {status_or_err}).")
        return True, f"Recurring digest broadcast successful (HTTP {status_or_err})."

    logger.error(f"Recurring digest broadcast failed: {status_or_err}")
    return False, f"Dispatch error: {status_or_err}"


def format_slack_payload(digest_data):
    """Formats digest statistics into Slack Block Kit payload."""
    rep = digest_data.get("replies", {})
    rat = digest_data.get("ratings", {})
    queue = digest_data.get("queue", {})

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚀 Tactful Humor Bot — Weekly Performance Digest",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Replies:* {rep.get('total_replies', 0)}\n*Likes:* {rep.get('total_likes', 0)}"
                },
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*Queue Dispatched:* {queue.get('sent', 0)}\n"
                        f"*Humor Approval:* {rat.get('approval_rate', 0)}%"
                    )
                }
            ]
        }
    ]

    top_humor = rat.get("top_humor", [])
    if top_humor:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Top Humor:* \"{top_humor[0].get('content', '')}\""
            }
        })

    return {"text": "Weekly Performance Digest", "blocks": blocks}


def format_discord_payload(digest_data):
    """Formats digest statistics into Discord embed payload."""
    rep = digest_data.get("replies", {})
    rat = digest_data.get("ratings", {})
    queue = digest_data.get("queue", {})

    likes_rts = f"{rep.get('total_likes', 0)} / {rep.get('total_retweets', 0)}"
    fields = [
        {"name": "Replies Sent", "value": str(rep.get("total_replies", 0)), "inline": True},
        {"name": "Likes / RTs", "value": likes_rts, "inline": True},
        {"name": "Humor Approval", "value": f"{rat.get('approval_rate', 0)}%", "inline": True},
        {"name": "Queue Dispatches", "value": str(queue.get("sent", 0)), "inline": True},
        {"name": "Pending in Queue", "value": str(queue.get("pending", 0)), "inline": True},
    ]

    top_humor = rat.get("top_humor", [])
    if top_humor:
        fields.append({"name": "Top Rated Humor", "value": f"\"{top_humor[0].get('content', '')}\"", "inline": False})

    embed = {
        "title": "🚀 Tactful Humor Bot — Weekly Performance Digest",
        "description": f"Performance summary over past {digest_data.get('window_days', 7)} days.",
        "color": 0x1DA1F2,
        "fields": fields,
        "timestamp": digest_data.get("generated_at", ""),
    }

    return {"embeds": [embed]}


def format_webhook_payload(digest_data, adapter="generic"):
    """Adapts digest data to specified platform webhook format."""
    adapter = (adapter or "generic").lower()
    if adapter == "slack":
        return format_slack_payload(digest_data)
    elif adapter == "discord":
        return format_discord_payload(digest_data)
    return {"digest": digest_data, "markdown": digest.export_digest_markdown(digest_data)}


def dispatch_webhook(webhook_url, payload, max_retries=2, timeout=5):
    """
    Sends JSON payload to the webhook endpoint using standard library urllib.
    Includes exponential backoff retry for network or 5xx server issues.
    """
    if not webhook_url:
        raise ValueError("Webhook URL cannot be empty.")

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "TactfulHumorBot-Digest/1.0"
        },
        method="POST"
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode()
                if 200 <= status < 300:
                    logger.info(f"Webhook dispatched successfully (HTTP {status}).")
                    return True, status
        except urllib.error.HTTPError as he:
            last_error = he
            logger.warning(f"Webhook HTTP error {he.code}: {he.reason} (attempt {attempt}/{max_retries})")
            if 400 <= he.code < 500:
                # Client error (e.g. 400 Bad Request, 404 Not Found); retries will not help
                break
        except Exception as e:
            last_error = e
            logger.warning(f"Webhook network error: {e} (attempt {attempt}/{max_retries})")

        if attempt < max_retries:
            time.sleep(0.5 * attempt)

    logger.error(f"Failed to dispatch webhook after retries: {last_error}")
    return False, str(last_error)
