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
