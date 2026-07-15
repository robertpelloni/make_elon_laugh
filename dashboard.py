from flask import Flask, render_template, jsonify
import sqlite3
import os
import db


app = Flask(__name__)


def get_db_stats():
    """Fetches statistics from the SQLite database."""
    stats = {"total_replies": 0, "recent_replies": []}
    db_path = db.DB_PATH

    if not os.path.exists(db_path):
        return stats

    try:
        with db.get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Get total count
            cursor.execute("SELECT COUNT(*) FROM replied_tweets")
            stats["total_replies"] = cursor.fetchone()[0]

            # Get 5 most recent replies
            cursor.execute("SELECT tweet_id, replied_at FROM replied_tweets ORDER BY replied_at DESC LIMIT 5")
            stats["recent_replies"] = [{"tweet_id": row[0], "replied_at": row[1]} for row in cursor.fetchall()]

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


if __name__ == '__main__':
    # Run on all interfaces so Docker port mapping works
    app.run(host='0.0.0.0', port=5000)
