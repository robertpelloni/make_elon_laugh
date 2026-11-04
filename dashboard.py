import collections
import logging
import os
import random
import sqlite3
import threading
import time
from flask import Flask, jsonify, render_template, request

import db
import joke_generator


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
    stats = {"total_replies": 0, "total_likes": 0, "total_retweets": 0, "recent_replies": []}
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
    Simulates content generation (joke or fact) with optional context tweet and sentiment evaluation.
    """
    data = request.get_json(silent=True) or {}
    context_tweet = data.get("context_tweet", "").strip() or None
    req_type = data.get("type", "auto").lower()

    if req_type == "joke":
        if context_tweet:
            content = joke_generator.fetch_llm_content(context_tweet, "joke")
            if content is None and os.environ.get("OPENAI_API_KEY"):
                # LLM filtered or returned SKIP
                return jsonify({"skipped": True, "message": "Context detected as serious/tragic."})
            if not content:
                content = random.choice(joke_generator.STATIC_JOKES)
        else:
            content = random.choice(joke_generator.STATIC_JOKES)
        return jsonify({"content": content, "content_type": "joke", "skipped": False})

    elif req_type == "fact":
        if context_tweet:
            content = joke_generator.fetch_llm_content(context_tweet, "fact")
            if content is None and os.environ.get("OPENAI_API_KEY"):
                return jsonify({"skipped": True, "message": "Context detected as serious/tragic."})
            if not content:
                content = random.choice(joke_generator.STATIC_FACTS)
        else:
            content = random.choice(joke_generator.STATIC_FACTS)
        return jsonify({"content": content, "content_type": "fact", "skipped": False})

    else:
        # Auto content generation using joke_generator.generate_content
        content = joke_generator.generate_content(context_tweet)
        # Check if content matches static facts
        ctype = "fact" if content in joke_generator.STATIC_FACTS else "joke"
        return jsonify({"content": content, "content_type": ctype, "skipped": False})


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
