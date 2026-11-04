import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = "bot_data.db"


@contextmanager
def get_db_connection(db_path=DB_PATH):
    """Context manager for SQLite database connections."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path=DB_PATH):
    """Initializes the SQLite database, creates tables, and performs migrations if needed."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Initial table creation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS replied_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    likes INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0
                )
            ''')

            # Migration check: Add engagement columns if upgrading from v0.1.0 to v0.2.0+
            cursor.execute("PRAGMA table_info(replied_tweets)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'likes' not in columns:
                cursor.execute("ALTER TABLE replied_tweets ADD COLUMN likes INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE replied_tweets ADD COLUMN retweets INTEGER DEFAULT 0")

            conn.commit()
        logger.info(f"Database initialized and migrated at {db_path}.")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def has_replied(tweet_id, db_path=DB_PATH):
    """Checks if the bot has already replied to the given tweet_id."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM replied_tweets WHERE tweet_id = ?", (str(tweet_id),))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Database error while checking tweet {tweet_id}: {e}")
        return False  # Fail safe: might result in duplicate reply if DB is corrupt, but prevents bot crash


def record_reply(tweet_id, db_path=DB_PATH):
    """Records a tweet_id into the database to prevent future duplicate replies."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO replied_tweets (tweet_id) VALUES (?)", (str(tweet_id),))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while recording reply for {tweet_id}: {e}")


def update_engagement(tweet_id, likes, retweets, db_path=DB_PATH):
    """Updates the engagement metrics for a previously recorded reply."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE replied_tweets SET likes = ?, retweets = ? WHERE tweet_id = ?",
                (likes, retweets, str(tweet_id))
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while updating engagement for {tweet_id}: {e}")


def get_tweets_for_engagement_polling(limit=10, db_path=DB_PATH):
    """Retrieves a list of recent tweet_ids to check for updated engagement metrics."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            # Fetch the most recent replies that might still be actively accumulating engagement
            cursor.execute("SELECT tweet_id FROM replied_tweets ORDER BY replied_at DESC LIMIT ?", (limit,))
            return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"Database error fetching tweets for engagement polling: {e}")
        return []
