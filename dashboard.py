from flask import Flask, render_template, jsonify
import sqlite3
import os
import db
import digest
import joke_generator
import scheduler


app = Flask(__name__)


def get_db_stats():
    """Fetches statistics from the SQLite database."""
    stats = {"total_replies": 0, "total_likes": 0, "total_retweets": 0, "recent_replies": []}
    db_path = db.DB_PATH

    if not os.path.exists(db_path):
        return stats

    try:
        with db.get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Get total count
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

    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")

    return stats


@app.route('/')
def index():
    """Renders the main dashboard UI."""
    stats = get_db_stats()
    # Mask API keys for security in the dashboard
    api_key_configured = bool(os.environ.get("API_KEY") and not os.environ.get("API_KEY").startswith("YOUR_"))

    config_status = {
        "api_key_configured": api_key_configured,
        "db_path": db.DB_PATH,
        "db_exists": os.path.exists(db.DB_PATH)
    }

    return render_template('index.html', stats=stats, config=config_status)


@app.route('/api/stats')
def api_stats():
    """Returns database stats as JSON for potential dynamic frontend updates."""
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
