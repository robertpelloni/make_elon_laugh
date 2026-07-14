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
    """Initializes the SQLite database and creates the replied_tweets table if it doesn't exist."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS replied_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
        logger.info(f"Database initialized at {db_path}.")
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
