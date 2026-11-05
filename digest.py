"""
Performance Digest Module.

Computes 7-day rolling performance digests across replies, public engagement,
joke approval ratings, and automated tweet queuing. Provides exportable markdown
and structured summaries for bot operators.
"""

import logging
from datetime import datetime, timezone
import db

logger = logging.getLogger(__name__)


def generate_performance_digest(db_path=db.DB_PATH, days=7):
    """
    Computes performance and engagement metrics over the preceding `days` window.

    Aggregates:
      - Replies sent within window, total likes, total retweets, average engagement.
      - Scheduled tweet queue activity (sent, pending, cancelled) and persona breakdown.
      - Humor approval rate, total ratings, and top-rated content snippets.
    """
    db.init_db(db_path)

    digest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "window_days": days,
        "replies": {
            "total_replies": 0,
            "total_likes": 0,
            "total_retweets": 0,
            "avg_likes_per_reply": 0.0,
            "avg_retweets_per_reply": 0.0,
        },
        "queue": {
            "total_scheduled": 0,
            "pending": 0,
            "sent": 0,
            "cancelled": 0,
            "persona_distribution": {},
        },
        "ratings": {
            "total_ratings": 0,
            "upvotes": 0,
            "downvotes": 0,
            "approval_rate": 0.0,
            "top_humor": [],
        },
    }

    try:
        with db.get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # 1. Replies & Engagement over rolling window
            cursor.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(likes), 0), COALESCE(SUM(retweets), 0)
                FROM replied_tweets
                WHERE replied_at >= datetime('now', '-' || ? || ' days')
                """,
                (str(days),),
            )
            rep_row = cursor.fetchone()
            if rep_row:
                tot_rep, tot_likes, tot_rts = rep_row
                digest["replies"]["total_replies"] = tot_rep
                digest["replies"]["total_likes"] = tot_likes
                digest["replies"]["total_retweets"] = tot_rts
                if tot_rep > 0:
                    digest["replies"]["avg_likes_per_reply"] = round(tot_likes / tot_rep, 1)
                    digest["replies"]["avg_retweets_per_reply"] = round(tot_rts / tot_rep, 1)

            # 2. Scheduled Tweet Queue Activity
            cursor.execute(
                """
                SELECT status, COUNT(*)
                FROM scheduled_tweets
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY status
                """,
                (str(days),),
            )
            for status, count in cursor.fetchall():
                digest["queue"]["total_scheduled"] += count
                if status in digest["queue"]:
                    digest["queue"][status] = count

            # Persona breakdown in queue
            cursor.execute(
                """
                SELECT persona, COUNT(*)
                FROM scheduled_tweets
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY persona
                """,
                (str(days),),
            )
            for persona, count in cursor.fetchall():
                digest["queue"]["persona_distribution"][persona] = count

            # 3. Community Ratings & Approval
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    COALESCE(SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN rating < 0 THEN 1 ELSE 0 END), 0)
                FROM joke_ratings
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                """,
                (str(days),),
            )
            rat_row = cursor.fetchone()
            if rat_row:
                tot_rat, up, down = rat_row
                digest["ratings"]["total_ratings"] = tot_rat
                digest["ratings"]["upvotes"] = up
                digest["ratings"]["downvotes"] = down
                if tot_rat > 0:
                    digest["ratings"]["approval_rate"] = round((up / tot_rat) * 100, 1)

            # Top rated content snippets
            cursor.execute(
                """
                SELECT content, rating, notes
                FROM joke_ratings
                WHERE rating > 0
                ORDER BY id DESC
                LIMIT 3
                """
            )
            digest["ratings"]["top_humor"] = [
                {"content": r[0], "rating": r[1], "notes": r[2]}
                for r in cursor.fetchall()
            ]

    except Exception as e:
        logger.error(f"Error compiling performance digest: {e}")

    return digest


def export_digest_markdown(digest):
    """Formats digest statistics into clean Markdown report for operators."""
    rep = digest.get("replies", {})
    queue = digest.get("queue", {})
    rat = digest.get("ratings", {})
    top_items = rat.get("top_humor", [])

    if top_items:
        top_humor_md = "\n".join([f"- *\"{item['content']}\"*" for item in top_items])
    else:
        top_humor_md = "- *None recorded yet.*"

    personas_md = ", ".join([f"{k}: {v}" for k, v in queue.get("persona_distribution", {}).items()]) or "None"

    md = f"""# 🚀 Tactful Humor Bot — Weekly Performance Digest
*Generated at: {digest.get('generated_at', 'N/A')} (Window: past {digest.get('window_days', 7)} days)*

## 📈 Public Replies & Engagement
- **Total Replies Dispatched:** {rep.get('total_replies', 0)}
- **Total Likes Accumulated:** {rep.get('total_likes', 0)} (avg {rep.get('avg_likes_per_reply', 0)} / reply)
- **Total Retweets:** {rep.get('total_retweets', 0)} (avg {rep.get('avg_retweets_per_reply', 0)} / reply)

## 📅 Scheduled Queue Operations
- **Total Scheduled Tweets:** {queue.get('total_scheduled', 0)}
  - Pending: {queue.get('pending', 0)}
  - Dispatched (Sent): {queue.get('sent', 0)}
  - Cancelled: {queue.get('cancelled', 0)}
- **Persona Distribution:** {personas_md}

## 🌟 Humor Approval & Ratings
- **Total Community Ratings:** {rat.get('total_ratings', 0)}
- **Humor Approval Rate:** {rat.get('approval_rate', 0)}% (+{rat.get('upvotes', 0)} / -{rat.get('downvotes', 0)})

### Top Rated Humor Snippets
{top_humor_md}

---
*Autonomous Tactful Humor Operations Console*
"""
    return md
