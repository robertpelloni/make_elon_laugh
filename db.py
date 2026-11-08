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

            # Table for operator/community ratings and reviews on humor and facts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS joke_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    rating INTEGER NOT NULL, -- 1 for upvote, -1 for downvote
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table for queued and scheduled tweets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_handle TEXT DEFAULT '@make_elon_laugh',
                    content TEXT NOT NULL,
                    scheduled_time TIMESTAMP NOT NULL,
                    persona TEXT DEFAULT 'tactful_engineer',
                    status TEXT DEFAULT 'pending', -- pending, sent, cancelled
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    media_theme TEXT DEFAULT NULL
                )
            ''')

            # Migration: Ensure account_handle and media_theme columns exist on scheduled_tweets
            cursor.execute("PRAGMA table_info(scheduled_tweets)")
            sched_cols = [row[1] for row in cursor.fetchall()]
            if 'account_handle' not in sched_cols:
                cursor.execute("ALTER TABLE scheduled_tweets ADD COLUMN account_handle TEXT DEFAULT '@make_elon_laugh'")
            if 'media_theme' not in sched_cols:
                cursor.execute("ALTER TABLE scheduled_tweets ADD COLUMN media_theme TEXT DEFAULT NULL")

            # Table for cross-platform syndicated posts (Mastodon, Bluesky)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS syndicated_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL, -- 'mastodon', 'bluesky'
                    remote_id TEXT,
                    content TEXT NOT NULL,
                    likes INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'sent', -- 'sent', 'failed', 'simulated'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table for target audience profiles and persona routing overrides
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS target_profiles (
                    target_id TEXT PRIMARY KEY,
                    username TEXT,
                    persona_override TEXT,
                    auto_reply_enabled INTEGER DEFAULT 1,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

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


def record_joke_rating(content, rating, notes=None, db_path=DB_PATH):
    """Records an operator or community rating (+1 or -1) for humor/fact content."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO joke_ratings (content, rating, notes) VALUES (?, ?, ?)",
                    (content.strip(), int(rating), notes.strip() if notes else None)
                )
            except sqlite3.OperationalError:
                # Table might not exist yet; auto-initialize and retry once
                init_db(db_path)
                cursor.execute(
                    "INSERT INTO joke_ratings (content, rating, notes) VALUES (?, ?, ?)",
                    (content.strip(), int(rating), notes.strip() if notes else None)
                )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"Database error while recording joke rating: {e}")
        return False


def get_joke_ratings(limit=10, db_path=DB_PATH):
    """Retrieves the most recent humor/fact ratings."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT id, content, rating, notes, created_at FROM joke_ratings ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            except sqlite3.OperationalError:
                init_db(db_path)
                cursor.execute(
                    "SELECT id, content, rating, notes, created_at FROM joke_ratings ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            return [
                {
                    "id": r[0],
                    "content": r[1],
                    "rating": r[2],
                    "notes": r[3],
                    "created_at": r[4]
                }
                for r in cursor.fetchall()
            ]
    except sqlite3.Error as e:
        logger.error(f"Database error fetching joke ratings: {e}")
        return []


def schedule_tweet(content, scheduled_time, persona="tactful_engineer", db_path=DB_PATH,
                   account_handle="@make_elon_laugh", media_theme=None):
    """
    Enqueues a tweet/joke for automated future posting with optional target account routing
    and visual meme card media theme.
    """
    try:
        clean_media = media_theme.strip().lower() if (media_theme and str(media_theme).strip()) else None
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            sql = (
                "INSERT INTO scheduled_tweets "
                "(content, scheduled_time, persona, status, account_handle, media_theme) "
                "VALUES (?, ?, ?, 'pending', ?, ?)"
            )
            try:
                cursor.execute(sql, (content.strip(), scheduled_time, persona, account_handle.strip(), clean_media))
            except sqlite3.OperationalError:
                init_db(db_path)
                cursor.execute(sql, (content.strip(), scheduled_time, persona, account_handle.strip(), clean_media))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Database error while scheduling tweet: {e}")
        return None


def get_scheduled_tweets(status=None, account_handle=None, limit=20, db_path=DB_PATH):
    """Retrieves scheduled tweets filtered optionally by status and target account."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                query = ("SELECT id, content, scheduled_time, persona, status, created_at, account_handle, media_theme "
                         "FROM scheduled_tweets")
                params = []
                conditions = []

                if status:
                    conditions.append("status = ?")
                    params.append(status)
                if account_handle:
                    conditions.append("account_handle = ?")
                    params.append(account_handle.strip())

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                if status == "pending":
                    query += " ORDER BY scheduled_time ASC LIMIT ?"
                else:
                    query += " ORDER BY scheduled_time DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, tuple(params))
            except sqlite3.OperationalError:
                init_db(db_path)
                return []

            return [
                {
                    "id": r[0],
                    "content": r[1],
                    "scheduled_time": r[2],
                    "persona": r[3],
                    "status": r[4],
                    "created_at": r[5],
                    "account_handle": r[6] if len(r) > 6 and r[6] else "@make_elon_laugh",
                    "media_theme": r[7] if len(r) > 7 and r[7] else None
                }
                for r in cursor.fetchall()
            ]
    except sqlite3.Error as e:
        logger.error(f"Database error fetching scheduled tweets: {e}")
        return []


def update_scheduled_tweet_status(tweet_id, new_status, db_path=DB_PATH):
    """Updates the status of a scheduled tweet (e.g., 'sent', 'cancelled')."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE scheduled_tweets SET status = ? WHERE id = ?",
                (new_status, int(tweet_id))
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error updating scheduled tweet {tweet_id}: {e}")
        return False


def record_syndicated_post(platform, content, remote_id=None, status="sent", likes=0, shares=0, db_path=DB_PATH):
    """Records a syndicated broadcast to SQLite."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            sql = (
                "INSERT INTO syndicated_posts (platform, remote_id, content, likes, shares, status) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            )
            try:
                cursor.execute(sql, (platform.lower().strip(), remote_id, content.strip(), likes, shares, status))
            except sqlite3.OperationalError:
                init_db(db_path)
                cursor.execute(sql, (platform.lower().strip(), remote_id, content.strip(), likes, shares, status))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Database error while recording syndicated post: {e}")
        return None


def update_syndication_metrics(post_id, likes, shares, db_path=DB_PATH):
    """Updates public engagement (likes/favorites and shares/reblogs) on a syndicated post."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE syndicated_posts SET likes = ?, shares = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (int(likes), int(shares), int(post_id))
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error updating syndication metrics for {post_id}: {e}")
        return False


def get_syndicated_posts_for_metrics_polling(limit=20, db_path=DB_PATH):
    """Retrieves recent active syndicated posts for metrics polling."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT id, platform, remote_id, content, likes, shares, status, created_at "
                    "FROM syndicated_posts WHERE status IN ('sent', 'simulated') "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            except sqlite3.OperationalError:
                init_db(db_path)
                return []

            return [
                {
                    "id": r[0],
                    "platform": r[1],
                    "remote_id": r[2],
                    "content": r[3],
                    "likes": r[4],
                    "shares": r[5],
                    "status": r[6],
                    "created_at": r[7]
                }
                for r in cursor.fetchall()
            ]
    except sqlite3.Error as e:
        logger.error(f"Database error fetching syndicated posts: {e}")
        return []


def get_syndication_summary_metrics(db_path=DB_PATH):
    """Calculates cumulative syndication counts and engagement by platform."""
    summary = {
        "total_posts": 0,
        "platforms": {
            "mastodon": {"posts": 0, "likes": 0, "shares": 0},
            "bluesky": {"posts": 0, "likes": 0, "shares": 0}
        }
    }
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT platform, COUNT(*), COALESCE(SUM(likes), 0), COALESCE(SUM(shares), 0) "
                    "FROM syndicated_posts GROUP BY platform"
                )
            except sqlite3.OperationalError:
                init_db(db_path)
                return summary

            for plat, count, likes, shares in cursor.fetchall():
                p_norm = plat.lower().strip()
                if p_norm not in summary["platforms"]:
                    summary["platforms"][p_norm] = {"posts": 0, "likes": 0, "shares": 0}
                summary["platforms"][p_norm]["posts"] = count
                summary["platforms"][p_norm]["likes"] = likes
                summary["platforms"][p_norm]["shares"] = shares
                summary["total_posts"] += count
    except sqlite3.Error as e:
        logger.error(f"Database error fetching syndication summary metrics: {e}")

    return summary


def get_target_profiles(db_path=DB_PATH):
    """Retrieves all target audience profiles with persona routing and settings."""
    profiles = []
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT target_id, username, persona_override, auto_reply_enabled, tags, created_at, updated_at "
                    "FROM target_profiles ORDER BY created_at ASC"
                )
            except sqlite3.OperationalError:
                init_db(db_path)
                return profiles

            for row in cursor.fetchall():
                profiles.append({
                    "target_id": str(row[0]),
                    "username": row[1] or "",
                    "persona_override": row[2] or "",
                    "auto_reply_enabled": bool(row[3]),
                    "tags": row[4] or "",
                    "created_at": str(row[5]),
                    "updated_at": str(row[6])
                })
    except sqlite3.Error as e:
        logger.error(f"Database error fetching target profiles: {e}")
    return profiles


def upsert_target_profile(target_id, username=None, persona_override=None,
                          auto_reply_enabled=1, tags="", db_path=DB_PATH):
    """
    Inserts or updates a target audience profile and persona routing configuration.
    """
    if not target_id or not str(target_id).strip():
        raise ValueError("Target ID cannot be empty.")

    t_id = str(target_id).strip()
    u_name = str(username).strip() if username else ""
    p_override = str(persona_override).strip() if persona_override else ""
    auto_reply = 1 if auto_reply_enabled else 0
    t_tags = str(tags).strip() if tags else ""

    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO target_profiles (
                        target_id, username, persona_override, auto_reply_enabled, tags, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(target_id) DO UPDATE SET
                        username=excluded.username,
                        persona_override=excluded.persona_override,
                        auto_reply_enabled=excluded.auto_reply_enabled,
                        tags=excluded.tags,
                        updated_at=CURRENT_TIMESTAMP
                ''', (t_id, u_name, p_override, auto_reply, t_tags))
            except sqlite3.OperationalError:
                init_db(db_path)
                cursor.execute('''
                    INSERT INTO target_profiles (
                        target_id, username, persona_override, auto_reply_enabled, tags, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(target_id) DO UPDATE SET
                        username=excluded.username,
                        persona_override=excluded.persona_override,
                        auto_reply_enabled=excluded.auto_reply_enabled,
                        tags=excluded.tags,
                        updated_at=CURRENT_TIMESTAMP
                ''', (t_id, u_name, p_override, auto_reply, t_tags))
            conn.commit()
            logger.info(f"Target profile upserted for target ID {t_id}.")
            return True
    except sqlite3.Error as e:
        logger.error(f"Database error upserting target profile {t_id}: {e}")
        return False


def delete_target_profile(target_id, db_path=DB_PATH):
    """Deletes a target profile by target_id."""
    if not target_id:
        return False
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM target_profiles WHERE target_id = ?", (str(target_id).strip(),))
            except sqlite3.OperationalError:
                init_db(db_path)
                return False
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error deleting target profile {target_id}: {e}")
        return False


def get_target_persona_override(target_id, db_path=DB_PATH):
    """
    Returns the persona override for a target user ID if set and auto_reply is enabled.
    Returns (persona_override, auto_reply_enabled).
    """
    if not target_id:
        return None, True
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT persona_override, auto_reply_enabled FROM target_profiles WHERE target_id = ?",
                    (str(target_id).strip(),)
                )
            except sqlite3.OperationalError:
                init_db(db_path)
                return None, True

            row = cursor.fetchone()
            if row:
                persona = row[0].strip() if (row[0] and row[0].strip()) else None
                auto_reply = bool(row[1])
                return persona, auto_reply
    except sqlite3.Error as e:
        logger.error(f"Database error checking persona override for {target_id}: {e}")

    return None, True
