import collections
import datetime
import json
import logging
import os
import random
import sqlite3
import threading
import time
from flask import Flask, jsonify, render_template, request

import db
import digest
import joke_generator
import scheduler
import splitter
import syndication
import webhook


app = Flask(__name__)

# Maintain an in-memory buffer of recent logs for live inspection on the dashboard
LOG_BUFFER = collections.deque(maxlen=100)


class InMemoryLogHandler(logging.Handler):
    """Captures application log records into an in-memory ring buffer for dashboard streaming."""
    def emit(self, record):
        try:
            msg = self.format(record)
            LOG_BUFFER.append(msg)
        except Exception:
            self.handleError(record)


# Attach handler to root logger
log_handler = InMemoryLogHandler()
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO)

# Default system theme preference: "dark" or "light"
CURRENT_THEME = os.environ.get("DASHBOARD_THEME", "dark")

# Default persona preference
CURRENT_PERSONA = os.environ.get("BOT_PERSONA", "tactful_engineer")

# Initial startup log
logging.info("Emperor Musk Bot Dashboard initialized and monitoring.")


def get_version():
    """Reads current version from VERSION.md."""
    version_file = os.path.join(os.path.dirname(__file__), "VERSION.md")
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return "0.8.0"


def get_db_stats():
    """Fetches statistics from the SQLite database."""
    stats = {
        "total_replies": 0,
        "total_likes": 0,
        "total_retweets": 0,
        "recent_replies": [],
        "total_ratings": 0,
        "positive_ratings": 0,
        "approval_rate": 100
    }
    db_path = db.DB_PATH

    if not os.path.exists(db_path):
        return stats

    try:
        with db.get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Get total count and cumulative engagement
            cursor.execute("SELECT COUNT(*), SUM(likes), SUM(retweets) FROM replied_tweets")
            row = cursor.fetchone()
            if row:
                stats["total_replies"] = row[0] or 0
                stats["total_likes"] = row[1] or 0
                stats["total_retweets"] = row[2] or 0

            # Get 5 most recent replies
            cursor.execute(
                "SELECT tweet_id, replied_at, likes, retweets "
                "FROM replied_tweets ORDER BY replied_at DESC LIMIT 5"
            )
            stats["recent_replies"] = [
                {"tweet_id": r[0], "replied_at": r[1], "likes": r[2], "retweets": r[3]}
                for r in cursor.fetchall()
            ]

            # Check if joke_ratings table exists before querying
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='joke_ratings'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*), SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) FROM joke_ratings")
                rating_row = cursor.fetchone()
                if rating_row and rating_row[0]:
                    stats["total_ratings"] = rating_row[0]
                    stats["positive_ratings"] = rating_row[1] or 0
                    stats["approval_rate"] = int((stats["positive_ratings"] / stats["total_ratings"]) * 100)

    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")

    return stats


@app.route('/')
def index():
    """Renders the consolidated single-page dashboard UI."""
    stats = get_db_stats()
    api_key_configured = bool(
        os.environ.get("API_KEY") and not os.environ.get("API_KEY").startswith("YOUR_")
    )
    target_user_ids = os.environ.get("TARGET_USER_IDS", "44196397")

    config_status = {
        "api_key_configured": api_key_configured,
        "db_path": db.DB_PATH,
        "db_exists": os.path.exists(db.DB_PATH),
        "target_user_ids": target_user_ids
    }

    return render_template(
        'index.html',
        stats=stats,
        config=config_status,
        version=get_version()
    )


@app.route('/api/ratings', methods=['GET', 'POST'])
def api_ratings():
    """
    Submits an operator rating (+1 upvote or -1 downvote) or lists recent ratings.
    """
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()
        rating = data.get("rating")
        notes = data.get("notes", "").strip() or None

        if not content:
            return jsonify({"success": False, "error": "Content is required for rating."}), 400

        try:
            rating_val = int(rating)
            if rating_val not in [1, -1]:
                return jsonify({"success": False, "error": "Rating must be 1 (upvote) or -1 (downvote)."}), 400
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Invalid rating format. Must be 1 or -1."}), 400

        success = db.record_joke_rating(content, rating_val, notes=notes)
        if success:
            logging.info(f"Recorded {'upvote (+1)' if rating_val > 0 else 'downvote (-1)'} for content preview.")
            return jsonify({
                "success": True,
                "message": "Rating recorded successfully.",
                "stats": get_db_stats()
            })
        return jsonify({"success": False, "error": "Failed to record rating in database."}), 500

    limit = request.args.get("limit", 10, type=int)
    return jsonify({
        "ratings": db.get_joke_ratings(limit=limit),
        "stats": get_db_stats()
    })


@app.route('/api/persona', methods=['GET', 'POST'])
def api_persona():
    """
    Retrieves or updates the active humor and content persona profile.
    """
    global CURRENT_PERSONA
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        persona = data.get("persona", "").lower().strip()
        if persona in joke_generator.PERSONAS:
            CURRENT_PERSONA = persona
            os.environ["BOT_PERSONA"] = persona
            logging.info(f"Bot humor persona switched to '{CURRENT_PERSONA}'.")
            return jsonify({
                "success": True,
                "persona": CURRENT_PERSONA,
                "details": joke_generator.PERSONAS[CURRENT_PERSONA]
            })
        return jsonify({
            "success": False,
            "error": f"Invalid persona. Choose from: {list(joke_generator.PERSONAS.keys())}"
        }), 400

    return jsonify({
        "current_persona": CURRENT_PERSONA,
        "personas": {
            k: {
                "display_name": v["display_name"],
                "description": v["description"]
            }
            for k, v in joke_generator.PERSONAS.items()
        }
    })


@app.route('/api/theme', methods=['GET', 'POST'])
def api_theme():
    """
    Retrieves or updates the system default UI theme preference ('dark' or 'light').
    """
    global CURRENT_THEME
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        theme = data.get("theme", "").lower().strip()
        if theme in ["dark", "light"]:
            CURRENT_THEME = theme
            logging.info(f"Dashboard theme preference updated to '{CURRENT_THEME}'.")
            return jsonify({"success": True, "theme": CURRENT_THEME})
        return jsonify({"success": False, "error": "Invalid theme. Must be 'dark' or 'light'."}), 400

    return jsonify({"theme": CURRENT_THEME})


@app.route('/api/split-preview', methods=['POST'])
def api_split_preview():
    """
    Simulates cross-platform thread chunking for arbitrary text input.
    Returns chunk count and lists of chunks per platform (Twitter, Bluesky, Mastodon).
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not isinstance(text, str):
        return jsonify({"error": "text must be a string"}), 400

    results = {
        "original_length": len(text),
        "twitter": {
            "limit": splitter.PLATFORM_LIMITS["twitter"],
            "chunks": splitter.split_for_platform(text, "twitter")
        },
        "bluesky": {
            "limit": splitter.PLATFORM_LIMITS["bluesky"],
            "chunks": splitter.split_for_platform(text, "bluesky")
        },
        "mastodon": {
            "limit": splitter.PLATFORM_LIMITS["mastodon"],
            "chunks": splitter.split_for_platform(text, "mastodon")
        }
    }
    return jsonify(results)


@app.route('/api/stats')
def api_stats():
    """Returns database stats as JSON for dynamic frontend updates."""
    return jsonify(get_db_stats())


@app.route('/api/logs')
def api_logs():
    """Returns recent log messages from the in-memory ring buffer."""
    return jsonify({"logs": list(LOG_BUFFER)})


@app.route('/api/test-generate', methods=['POST'])
def api_test_generate():
    """
    Simulates content generation (joke or fact) with optional context tweet, sentiment evaluation, and persona.
    """
    data = request.get_json(silent=True) or {}
    context_tweet = data.get("context_tweet", "").strip() or None
    req_type = data.get("type", "auto").lower()
    persona = data.get("persona", CURRENT_PERSONA).lower().strip()
    pdata = joke_generator.get_persona(persona)

    if req_type == "joke":
        if context_tweet:
            content = joke_generator.fetch_llm_content(context_tweet, "joke", persona=persona)
            if content is None and os.environ.get("OPENAI_API_KEY"):
                # LLM filtered or returned SKIP
                return jsonify({"skipped": True, "message": "Context detected as serious/tragic."})
            if not content:
                content = random.choice(pdata["jokes"])
        else:
            content = random.choice(pdata["jokes"])
        return jsonify({"content": content, "content_type": "joke", "persona": persona, "skipped": False})

    elif req_type == "fact":
        if context_tweet:
            content = joke_generator.fetch_llm_content(context_tweet, "fact", persona=persona)
            if content is None and os.environ.get("OPENAI_API_KEY"):
                return jsonify({"skipped": True, "message": "Context detected as serious/tragic."})
            if not content:
                content = random.choice(pdata["facts"])
        else:
            content = random.choice(pdata["facts"])
        return jsonify({"content": content, "content_type": "fact", "persona": persona, "skipped": False})

    else:
        # Auto content generation using joke_generator.generate_content
        content = joke_generator.generate_content(context_tweet, persona=persona)
        ctype = "fact" if content in pdata["facts"] else "joke"
        return jsonify({"content": content, "content_type": ctype, "persona": persona, "skipped": False})


@app.route('/api/test-generate-meme', methods=['POST'])
def api_test_generate_meme():
    """
    Generates a visual meme card as a base64 PNG image based on content text.
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        text = joke_generator.generate_content()

    try:
        b64_image = joke_generator.generate_meme_card_b64(text)
        return jsonify({
            "success": True,
            "text": text,
            "image_b64": b64_image
        })
    except Exception as e:
        app.logger.error(f"Meme card generation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """Gets or updates target user IDs in runtime environment."""
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        target_ids = data.get("target_user_ids", "").strip()
        if not target_ids:
            return jsonify({"success": False, "error": "Target user IDs cannot be empty."}), 400

        # Validate format: comma-separated list of IDs
        cleaned_ids = [tid.strip() for tid in target_ids.split(",") if tid.strip()]
        if not cleaned_ids:
            return jsonify({"success": False, "error": "At least one target user ID is required."}), 400

        os.environ["TARGET_USER_IDS"] = ",".join(cleaned_ids)
        logging.info(f"Target user IDs updated via dashboard: {os.environ['TARGET_USER_IDS']}")
        return jsonify({"success": True, "target_user_ids": os.environ["TARGET_USER_IDS"]})

    return jsonify({
        "target_user_ids": os.environ.get("TARGET_USER_IDS", "44196397"),
        "db_path": db.DB_PATH,
        "version": get_version()
    })


@app.route('/api/targets', methods=['GET', 'POST', 'DELETE'])
def api_targets():
    """
    Manages target audience profiles and per-target persona routing.
    GET: Returns list of all configured target profiles.
    POST: Inserts or updates a target profile.
          Body: {
            "target_id": "...",
            "username": "...",
            "persona_override": "tactful_engineer|witty_ai|deadpan_astronomer|",
            "auto_reply_enabled": true|false,
            "tags": "..."
          }
    DELETE: Deletes a target profile. Body: {"target_id": "..."}
    """
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        target_id = str(data.get("target_id", "")).strip()
        if not target_id:
            return jsonify({"success": False, "error": "Target ID is required."}), 400

        username = str(data.get("username", "")).strip()
        persona = str(data.get("persona_override", "")).strip()
        if persona and persona not in joke_generator.PERSONAS:
            return jsonify({
                "success": False,
                "error": f"Invalid persona '{persona}'. Allowed: {list(joke_generator.PERSONAS.keys())}"
            }), 400

        auto_reply = data.get("auto_reply_enabled", True)
        tags = str(data.get("tags", "")).strip()

        ok = db.upsert_target_profile(
            target_id=target_id,
            username=username,
            persona_override=persona,
            auto_reply_enabled=1 if auto_reply else 0,
            tags=tags
        )
        if ok:
            return jsonify({"success": True, "message": f"Target profile {target_id} saved."})
        return jsonify({"success": False, "error": "Failed to save target profile."}), 500

    elif request.method == 'DELETE':
        data = request.get_json(silent=True) or {}
        target_id = str(data.get("target_id", "")).strip()
        if not target_id:
            return jsonify({"success": False, "error": "Target ID is required."}), 400

        deleted = db.delete_target_profile(target_id)
        if deleted:
            return jsonify({"success": True, "message": f"Target profile {target_id} deleted."})
        return jsonify({"success": False, "error": f"Target profile {target_id} not found."}), 404

    # GET
    profiles = db.get_target_profiles()
    return jsonify({
        "success": True,
        "profiles": profiles,
        "allowed_personas": list(joke_generator.PERSONAS.keys())
    })


@app.route('/api/run-check', methods=['POST'])
def api_run_check():
    """
    Executes an on-demand dry-run cycle simulation and logs findings.
    """
    try:
        db.init_db()
        test_tweet_id = random.randint(100000, 999999)
        test_tweet_text = f"Simulated orbital test mission at {time.strftime('%H:%M:%S')}! 🚀"
        logging.info(f"⚡ [Dry-Run Check] Triggered via Dashboard for Tweet ID {test_tweet_id}")

        content = joke_generator.generate_content(test_tweet_text)
        db.record_reply(test_tweet_id)
        # Record small initial engagement for preview
        db.update_engagement(test_tweet_id, likes=random.randint(1, 10), retweets=random.randint(0, 3))

        logging.info(f"⚡ [Dry-Run Check] Verified reply recorded: '{content}'")
        return jsonify({
            "success": True,
            "message": f"Dry-run cycle executed. Logged reply for simulated tweet {test_tweet_id}.",
            "tweet_id": test_tweet_id,
            "reply": content
        })
    except Exception as e:
        logging.error(f"Error in dry-run check: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/schedule/optimal-slot", methods=["GET"])
def api_schedule_optimal_slot():
    """
    Returns the recommended optimal post scheduling slot based on audience activity
    and space/tech engagement windows.
    """
    from scheduler import recommend_optimal_post_slot
    slot_info = recommend_optimal_post_slot()
    return jsonify({"success": True, "slot": slot_info})


@app.route('/api/schedule', methods=['GET', 'POST', 'DELETE'])
def api_schedule():
    """
    Manages scheduled and queued tweets.
    GET: Returns list of scheduled tweets.
    POST: Enqueues a new scheduled tweet.
    DELETE: Cancels a scheduled tweet by ID.
    """
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()
        scheduled_time = data.get("scheduled_time", "").strip()
        persona = data.get("persona", CURRENT_PERSONA).strip()

        if not content:
            return jsonify({"success": False, "error": "Content cannot be empty."}), 400
        if not scheduled_time:
            return jsonify({"success": False, "error": "Scheduled time is required (YYYY-MM-DD HH:MM)."}), 400

        try:
            tweet_id = scheduler.enqueue_scheduled_tweet(content, scheduled_time, persona=persona)
            if tweet_id:
                logging.info(f"Enqueued scheduled tweet ID {tweet_id} for {scheduled_time}.")
                return jsonify({
                    "success": True,
                    "id": tweet_id,
                    "message": "Tweet scheduled successfully.",
                    "scheduled_tweets": db.get_scheduled_tweets(limit=10)
                })
            return jsonify({"success": False, "error": "Database error while enqueuing tweet."}), 500
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    elif request.method == 'DELETE':
        data = request.get_json(silent=True) or {}
        tweet_id = data.get("id")
        if not tweet_id:
            return jsonify({"success": False, "error": "Tweet ID is required for cancellation."}), 400

        updated = db.update_scheduled_tweet_status(tweet_id, "cancelled")
        if updated:
            logging.info(f"Cancelled scheduled tweet ID {tweet_id}.")
            return jsonify({"success": True, "message": f"Tweet {tweet_id} cancelled."})
        return jsonify({"success": False, "error": f"Failed to cancel tweet {tweet_id}."}), 404

    # GET request
    status = request.args.get("status")
    limit = request.args.get("limit", 20, type=int)
    tweets = db.get_scheduled_tweets(status=status, limit=limit)

    # Compute calendar distribution across 7 days of current week (Monday=0 to Sunday=6)
    calendar_breakdown = {day: 0 for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
    day_abbrs = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    total_pending = 0
    total_sent = 0
    total_cancelled = 0

    all_recent = db.get_scheduled_tweets(limit=100)
    for t in all_recent:
        st = t.get("status", "pending")
        if st == "pending":
            total_pending += 1
            # Add to day breakdown if parsable
            try:
                date_str = t.get("scheduled_time", "").split(" ")[0]
                dt = time.strptime(date_str, "%Y-%m-%d")
                weekday = day_abbrs[dt.tm_wday]
                calendar_breakdown[weekday] += 1
            except Exception:
                pass
        elif st == "sent":
            total_sent += 1
        elif st == "cancelled":
            total_cancelled += 1

    return jsonify({
        "scheduled_tweets": tweets,
        "metrics": {
            "pending": total_pending,
            "sent": total_sent,
            "cancelled": total_cancelled
        },
        "weekly_calendar": calendar_breakdown
    })


@app.route('/api/digest', methods=['GET'])
def api_digest():
    """
    Returns rolling weekly performance analytics and summary metrics.
    Query params:
      days: integer window length (default 7)
      format: 'json' (default) or 'markdown'
    """
    days = request.args.get('days', default=7, type=int)
    fmt = request.args.get('format', default='json', type=str).lower()

    summary = digest.generate_performance_digest(days=days)

    if fmt == 'markdown':
        md_text = digest.export_digest_markdown(summary)
        return jsonify({
            "success": True,
            "format": "markdown",
            "markdown": md_text,
            "digest": summary
        })

    return jsonify({
        "success": True,
        "format": "json",
        "digest": summary
    })


@app.route('/api/digest/download', methods=['GET'])
def api_digest_download():
    """
    Directly streams the performance digest as a downloadable attachment with robust error resilience.
    Query params:
      days: integer window length (default 7, bounded 1-365)
      format: 'markdown' (default, .md), 'html' (.html), or 'json' (.json)
      prefix: optional filename prefix (default 'digest')
    """
    try:
        days = request.args.get('days', default=7, type=int)
        if days < 1:
            days = 7
        elif days > 365:
            days = 365
    except (TypeError, ValueError):
        days = 7

    prefix = request.args.get('prefix', default='digest', type=str).strip()
    clean_prefix = "".join(c for c in prefix if c.isalnum() or c in ("-", "_")).strip() or "digest"

    fmt = request.args.get('format', default='markdown', type=str).lower().strip()
    timestamp_slug = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")

    try:
        summary = digest.generate_performance_digest(days=days)
    except Exception as e:
        app.logger.error(f"Error generating performance digest for download: {e}")
        return jsonify({
            "success": False,
            "error": f"Failed to generate digest: {str(e)}"
        }), 500

    try:
        if fmt == 'json':
            content = json.dumps(summary, indent=2)
            filename = f"{clean_prefix}_{timestamp_slug}.json"
            mimetype = "application/json"
        elif fmt == 'html':
            content = digest.export_digest_html(summary)
            filename = f"{clean_prefix}_{timestamp_slug}.html"
            mimetype = "text/html"
        else:
            content = digest.export_digest_markdown(summary)
            filename = f"{clean_prefix}_{timestamp_slug}.md"
            mimetype = "text/markdown"

        response = app.response_class(
            response=content,
            status=200,
            mimetype=mimetype
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        app.logger.error(f"Error exporting digest payload format '{fmt}': {e}")
        return jsonify({
            "success": False,
            "error": f"Failed to export digest formatted as '{fmt}': {str(e)}"
        }), 500


@app.route('/api/syndication', methods=['GET', 'POST'])
def api_syndication():
    """
    Manages social federation syndication settings and on-demand broadcast.
    GET: Returns current syndication configuration and status for Mastodon & Bluesky.
    POST: Updates configuration or triggers immediate test broadcast.
    """
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        mastodon_enabled = data.get("mastodon_enabled")
        mastodon_url = data.get("mastodon_instance_url")
        mastodon_token = data.get("mastodon_access_token")
        bluesky_enabled = data.get("bluesky_enabled")
        bluesky_handle = data.get("bluesky_handle")
        bluesky_password = data.get("bluesky_app_password")
        broadcast_now = data.get("broadcast_now", False)
        sample_text = data.get("text", "").strip()

        if mastodon_enabled is not None:
            syndication.MASTODON_ENABLED = bool(mastodon_enabled)
        if mastodon_url is not None:
            syndication.MASTODON_INSTANCE_URL = mastodon_url.strip()
        if mastodon_token is not None:
            syndication.MASTODON_ACCESS_TOKEN = mastodon_token.strip()
        if bluesky_enabled is not None:
            syndication.BLUESKY_ENABLED = bool(bluesky_enabled)
        if bluesky_handle is not None:
            syndication.BLUESKY_HANDLE = bluesky_handle.strip()
        if bluesky_password is not None:
            syndication.BLUESKY_APP_PASSWORD = bluesky_password.strip()

        if broadcast_now:
            text_to_send = sample_text or joke_generator.generate_content()
            results = syndication.dispatch_syndicated_post(text_to_send, dry_run=True)
            return jsonify({
                "success": True,
                "message": "Broadcast test executed (dry-run).",
                "text": text_to_send,
                "results": results
            })

        return jsonify({
            "success": True,
            "message": "Syndication settings updated.",
            "mastodon_enabled": syndication.MASTODON_ENABLED,
            "bluesky_enabled": syndication.BLUESKY_ENABLED
        })

    # GET request: return status and masked credentials
    mast_token = syndication.MASTODON_ACCESS_TOKEN
    masked_mast_token = ""
    if mast_token:
        masked_mast_token = (mast_token[:4] + "..." + mast_token[-4:]) if len(mast_token) > 8 else "***"

    bsky_pwd = syndication.BLUESKY_APP_PASSWORD
    masked_bsky_pwd = ("***" if bsky_pwd else "")

    return jsonify({
        "mastodon": {
            "enabled": syndication.MASTODON_ENABLED,
            "instance_url": syndication.MASTODON_INSTANCE_URL,
            "token_configured": bool(mast_token),
            "masked_token": masked_mast_token
        },
        "bluesky": {
            "enabled": syndication.BLUESKY_ENABLED,
            "handle": syndication.BLUESKY_HANDLE,
            "password_configured": bool(bsky_pwd),
            "masked_password": masked_bsky_pwd
        },
        "last_post": syndication.LAST_SYNDICATED_POST
    })


@app.route('/api/syndication/metrics', methods=['GET'])
def api_syndication_metrics():
    """
    Returns platform-by-platform syndication counts and engagement metrics,
    along with any active federation anomaly alerts.
    """
    summary = db.get_syndication_summary_metrics()
    recent = db.get_syndicated_posts_for_metrics_polling(limit=10)

    perf_digest = digest.generate_performance_digest()
    fed_alerts = [
        a for a in perf_digest.get("alerts", [])
        if a.get("type", "").startswith("federation_")
    ]

    return jsonify({
        "success": True,
        "summary": summary,
        "recent_posts": recent,
        "federation_alerts": fed_alerts,
        "federation_health": perf_digest.get("health_scorecard", {}).get("federation_health", "Idle")
    })


@app.route('/api/syndication/poll', methods=['POST'])
def api_syndication_poll():
    """
    Triggers an on-demand engagement poll for all active syndicated posts across Mastodon and Bluesky.
    """
    poll_results = syndication.poll_all_syndicated_metrics(limit=25, dry_run=True)
    summary = db.get_syndication_summary_metrics()
    return jsonify({
        "success": True,
        "message": (
            f"Polled {poll_results.get('updated_posts', 0)} syndicated posts: "
            f"+{poll_results.get('likes_polled', 0)} likes, "
            f"+{poll_results.get('shares_polled', 0)} shares."
        ),
        "poll_results": poll_results,
        "summary": summary
    })


@app.route('/api/webhook', methods=['GET', 'POST'])
def api_webhook():
    """
    Manages digest webhook delivery configuration and manual test dispatch.
    GET: Returns current webhook configuration (masked URL, secret status, auto dispatch status, interval).
    POST: Updates webhook URL, secret, adapter, auto-dispatch switch, interval, or triggers test dispatch.
          Body: {
            "webhook_url": "...",
            "webhook_secret": "...",
            "adapter": "slack|discord|generic",
            "auto_dispatch": true|false,
            "interval_hours": 24|72|168,
            "dispatch_now": true|false
          }
    """
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        new_url = data.get("webhook_url")
        new_secret = data.get("webhook_secret")
        new_adapter = data.get("adapter")
        auto_dispatch = data.get("auto_dispatch")
        interval_hours = data.get("interval_hours")
        dispatch_now = data.get("dispatch_now", False)

        if new_url is not None:
            webhook.DEFAULT_WEBHOOK_URL = new_url.strip()
        if new_secret is not None:
            webhook.DEFAULT_WEBHOOK_SECRET = new_secret.strip()
        if new_adapter is not None:
            webhook.DEFAULT_ADAPTER = new_adapter.strip().lower()
        if auto_dispatch is not None:
            webhook.AUTO_DISPATCH_ENABLED = bool(auto_dispatch)
        if interval_hours is not None:
            try:
                val = int(interval_hours)
                if val >= 1:
                    webhook.DISPATCH_INTERVAL_HOURS = val
            except (ValueError, TypeError):
                pass

        if dispatch_now:
            target_url = webhook.DEFAULT_WEBHOOK_URL
            if not target_url:
                return jsonify({"success": False, "error": "No webhook URL configured."}), 400

            # Generate latest 7-day digest
            summary = digest.generate_performance_digest(days=7)
            payload = webhook.format_webhook_payload(summary, adapter=webhook.DEFAULT_ADAPTER)

            success, status_or_err = webhook.dispatch_webhook(
                target_url,
                payload,
                secret=webhook.DEFAULT_WEBHOOK_SECRET
            )
            if success:
                webhook.LAST_DISPATCH_TIMESTAMP = time.time()
                return jsonify({
                    "success": True,
                    "message": f"Webhook dispatched successfully (HTTP {status_or_err}).",
                    "adapter": webhook.DEFAULT_ADAPTER,
                    "signed": bool(webhook.DEFAULT_WEBHOOK_SECRET)
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"Webhook dispatch failed: {status_or_err}"
                }), 502

        return jsonify({
            "success": True,
            "message": "Webhook settings updated.",
            "adapter": webhook.DEFAULT_ADAPTER,
            "auto_dispatch": webhook.AUTO_DISPATCH_ENABLED,
            "interval_hours": webhook.DISPATCH_INTERVAL_HOURS,
            "has_secret": bool(webhook.DEFAULT_WEBHOOK_SECRET)
        })

    # GET: return masked URL, secret status, and dispatch configuration for operator review
    url = webhook.DEFAULT_WEBHOOK_URL
    masked_url = ""
    if url:
        if len(url) > 16:
            masked_url = url[:10] + "..." + url[-6:]
        else:
            masked_url = "***"

    secret = webhook.DEFAULT_WEBHOOK_SECRET
    masked_secret = ""
    if secret:
        if len(secret) > 8:
            masked_secret = secret[:3] + "..." + secret[-3:]
        else:
            masked_secret = "***"

    return jsonify({
        "configured": bool(url),
        "masked_url": masked_url,
        "has_secret": bool(secret),
        "masked_secret": masked_secret,
        "adapter": webhook.DEFAULT_ADAPTER,
        "auto_dispatch": webhook.AUTO_DISPATCH_ENABLED,
        "interval_hours": webhook.DISPATCH_INTERVAL_HOURS,
        "last_dispatch": webhook.LAST_DISPATCH_TIMESTAMP
    })


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    """
    Gracefully stops the web dashboard and notifies operators.
    """
    logging.info("🛑 Graceful server shutdown requested via API.")

    def schedule_stop():
        time.sleep(1)
        os._exit(0)

    # Trigger exit in background thread to allow response to send
    threading.Thread(target=schedule_stop, daemon=True).start()
    return jsonify({"success": True, "message": "Emperor Musk Bot server is shutting down gracefully."})


if __name__ == '__main__':
    # Run on all interfaces so Docker port mapping works
    app.run(host='0.0.0.0', port=5000)
