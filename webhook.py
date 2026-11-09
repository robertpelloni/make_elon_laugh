"""
Digest Webhook Dispatcher Module.

Formats and dispatches weekly performance digests to Discord, Slack,
or generic HTTP webhook endpoints using standard library urllib.
Includes exponential backoff retries for transient HTTP errors.
"""

import hashlib
import hmac
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
DEFAULT_WEBHOOK_SECRET = os.environ.get("DIGEST_WEBHOOK_SECRET", "")
DEFAULT_ADAPTER = os.environ.get("DIGEST_WEBHOOK_ADAPTER", "generic").lower()
AUTO_DISPATCH_ENABLED = os.environ.get("DIGEST_AUTO_DISPATCH", "false").lower() in ["true", "1", "yes"]
DISPATCH_INTERVAL_HOURS = int(os.environ.get("DIGEST_INTERVAL_HOURS", "168"))  # default 7 days (168 hours)
LAST_DISPATCH_TIMESTAMP = 0.0


def compute_webhook_signature(payload_bytes, secret):
    """
    Computes an HMAC-SHA256 signature for outgoing webhook payload verification.
    Returns sha256=<hex_digest> format conforming to industry webhook standards (e.g., GitHub/Shopify).
    """
    if not secret:
        return ""
    if isinstance(secret, str):
        secret_bytes = secret.encode("utf-8")
    else:
        secret_bytes = bytes(secret)

    mac = hmac.new(secret_bytes, payload_bytes, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


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

    success, status_or_err = dispatch_webhook(
        DEFAULT_WEBHOOK_URL,
        payload,
        secret=DEFAULT_WEBHOOK_SECRET
    )
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

    alerts = digest_data.get("alerts", [])

    media_dist = queue.get("media_distribution", {})
    single_cnt = media_dist.get("single", 0)
    comp_cnt = media_dist.get("composite", 0)

    dlq = digest_data.get("dlq", {})
    dlq_pend = dlq.get("pending", 0)
    dlq_exh = dlq.get("exhausted", 0)
    dlq_rep = dlq.get("replayed", 0)

    cbs = digest_data.get("circuit_breakers", {})
    cb_vals = list(cbs.values()) if isinstance(cbs, dict) else (cbs or [])
    open_cbs = [c for c in cb_vals if isinstance(c, dict) and c.get("state") == "OPEN"]
    cb_summary = "Nominal"
    if open_cbs:
        open_names = ", ".join([c.get("platform", "").capitalize() for c in open_cbs])
        cb_summary = f"⚠️ {len(open_cbs)} OPEN ({open_names})"

    heatmap = digest_data.get("heatmap", {})
    peak_win = heatmap.get("peak_window_label", "17:00 - 18:00 UTC")
    recs = digest_data.get("recommendations", [])

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚀 Tactful Humor Bot — Weekly Performance Digest" + (" ⚠️ Alerts Active" if alerts else ""),
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
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Media Queue:*\nSingle: {single_cnt} | Composite: {comp_cnt}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*DLQ Deliverability:*\nPend: {dlq_pend} | Exh: {dlq_exh} | Repl: {dlq_rep}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Circuit Breakers:*\n{cb_summary}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Peak Engagement Slot:*\n⏱️ {peak_win}"
                }
            ]
        }
    ]

    pb = digest_data.get("platform_breakdowns", {})
    if pb:
        pb_parts = [
            f"{info.get('display_name', k)}: {info.get('avg_engagement_per_post', 0.0)}/post "
            f"({info.get('velocity_tier', 'Low')})"
            for k, info in sorted(pb.items())
        ]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*⚡ Platform Velocities:* " + " | ".join(pb_parts)
            }
        })

    if alerts:
        alert_text = "\n".join([
            f"• *[{a.get('level', 'warning').upper()}]* {a.get('message')}"
            for a in alerts
        ])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*⚠️ Active Alerts:*\n{alert_text}"
            }
        })

    top_humor = rat.get("top_humor", [])
    if top_humor:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Top Humor:* \"{top_humor[0].get('content', '')}\""
            }
        })

    top_rep = rep.get("top_reply")
    if top_rep:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Top Reply:* Tweet `{top_rep.get('tweet_id')}` "
                    f"({top_rep.get('likes', 0)} likes, {top_rep.get('retweets', 0)} RTs)"
                )
            }
        })

    if recs:
        recs_text = "\n".join([f"• {r}" for r in recs[:2]])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*💡 Engagement Insights:*\n{recs_text}"
            }
        })

    return {"text": "Weekly Performance Digest", "blocks": blocks}


def format_discord_payload(digest_data):
    """Formats digest statistics into Discord embed payload."""
    rep = digest_data.get("replies", {})
    rat = digest_data.get("ratings", {})
    queue = digest_data.get("queue", {})

    likes_rts = f"{rep.get('total_likes', 0)} / {rep.get('total_retweets', 0)}"
    alerts = digest_data.get("alerts", [])
    color = 0xef4444 if any(a.get("level") == "critical" for a in alerts) else (0xf59e0b if alerts else 0x1DA1F2)

    media_dist = queue.get("media_distribution", {})
    single_cnt = media_dist.get("single", 0)
    comp_cnt = media_dist.get("composite", 0)

    dlq = digest_data.get("dlq", {})
    dlq_pend = dlq.get("pending", 0)
    dlq_exh = dlq.get("exhausted", 0)
    dlq_rep = dlq.get("replayed", 0)

    cbs_discord = digest_data.get("circuit_breakers", {})
    cb_vals_discord = list(cbs_discord.values()) if isinstance(cbs_discord, dict) else (cbs_discord or [])
    open_cbs_discord = [c for c in cb_vals_discord if isinstance(c, dict) and c.get("state") == "OPEN"]
    cb_summary = "Nominal (All Closed)"
    if open_cbs_discord:
        open_names = ", ".join([c.get("platform", "").capitalize() for c in open_cbs_discord])
        cb_summary = f"⚠️ {len(open_cbs_discord)} OPEN ({open_names})"

    heatmap = digest_data.get("heatmap", {})
    peak_win = heatmap.get("peak_window_label", "17:00 - 18:00 UTC")
    recs = digest_data.get("recommendations", [])

    fields = [
        {"name": "Replies Sent", "value": str(rep.get("total_replies", 0)), "inline": True},
        {"name": "Likes / RTs", "value": likes_rts, "inline": True},
        {"name": "Humor Approval", "value": f"{rat.get('approval_rate', 0)}%", "inline": True},
        {"name": "Queue Dispatches", "value": str(queue.get("sent", 0)), "inline": True},
        {"name": "Pending in Queue", "value": str(queue.get("pending", 0)), "inline": True},
        {"name": "Media Distribution", "value": f"Single: {single_cnt} | Composite: {comp_cnt}", "inline": True},
        {"name": "DLQ Deliverability", "value": f"Pend: {dlq_pend} | Exh: {dlq_exh} | Repl: {dlq_rep}", "inline": True},
        {"name": "Circuit Breakers", "value": cb_summary, "inline": True},
        {"name": "Peak Engagement", "value": f"⏱️ {peak_win}", "inline": True},
    ]

    if recs:
        recs_desc = "\n".join([f"• {r}" for r in recs[:2]])
        fields.append({"name": "💡 Strategic Insights", "value": recs_desc, "inline": False})

    pb_discord = digest_data.get("platform_breakdowns", {})
    if pb_discord:
        pb_disc_desc = "\n".join([
            f"• **{info.get('display_name', k)}**: {info.get('avg_engagement_per_post', 0.0)} eng/post "
            f"({info.get('velocity_tier', 'Low')} tier, {info.get('share_of_total_posts_pct', 0.0)}% share)"
            for k, info in sorted(pb_discord.items())
        ])
        fields.append({"name": "⚡ Platform Velocities", "value": pb_disc_desc, "inline": False})

    if alerts:
        alert_msgs = "\n".join([
            f"• **[{a.get('level', 'warning').upper()}]** {a.get('message')}"
            for a in alerts
        ])
        fields.append({"name": "⚠️ Active Alerts", "value": alert_msgs, "inline": False})

    top_humor = rat.get("top_humor", [])
    if top_humor:
        fields.append({"name": "Top Rated Humor", "value": f"\"{top_humor[0].get('content', '')}\"", "inline": False})

    top_rep = rep.get("top_reply")
    if top_rep:
        fields.append({
            "name": "Top Performing Reply",
            "value": (
                f"Tweet `{top_rep.get('tweet_id')}` "
                f"({top_rep.get('likes', 0)} likes, {top_rep.get('retweets', 0)} RTs)"
            ),
            "inline": False
        })

    embed = {
        "title": "🚀 Tactful Humor Bot — Weekly Performance Digest",
        "description": f"Performance summary over past {digest_data.get('window_days', 7)} days.",
        "color": color,
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


def dispatch_webhook(webhook_url, payload, max_retries=2, timeout=5, secret=None):
    """
    Sends JSON payload to the webhook endpoint using standard library urllib.
    Includes exponential backoff retry for network or 5xx server issues.
    Optionally computes and attaches cryptographic HMAC-SHA256 signature headers:
      - X-Hub-Signature-256: sha256=<hex_digest>
      - X-Signature-Timestamp: <unix_epoch_seconds>
    """
    if not webhook_url:
        raise ValueError("Webhook URL cannot be empty.")

    data_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "TactfulHumorBot-Digest/1.0"
    }

    signing_secret = secret if secret is not None else DEFAULT_WEBHOOK_SECRET
    if signing_secret:
        timestamp_str = str(int(time.time()))
        signature = compute_webhook_signature(data_bytes, signing_secret)
        headers["X-Hub-Signature-256"] = signature
        headers["X-Signature-Timestamp"] = timestamp_str

    req = urllib.request.Request(
        webhook_url,
        data=data_bytes,
        headers=headers,
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
