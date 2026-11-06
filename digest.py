"""
Performance Digest Module.

Computes multi-window performance digests across replies, public engagement,
joke approval ratings, automated tweet queuing, and system operational health.
Provides previous-period delta trend comparisons, operational health scorecards,
and exportable markdown and structured summaries for bot operators.
"""

import logging
from datetime import datetime, timezone
import db

logger = logging.getLogger(__name__)


def _compute_delta(current, previous):
    """Computes difference and percentage change between two numeric values."""
    diff = current - previous
    if previous > 0:
        pct = round((diff / previous) * 100, 1)
    else:
        pct = 100.0 if current > 0 else 0.0
    return {"current": current, "previous": previous, "diff": diff, "pct": pct}


def generate_performance_digest(db_path=db.DB_PATH, days=7):
    """
    Computes performance and engagement metrics over the preceding `days` window,
    as well as delta trends comparing with the immediately preceding window of identical duration.

    Aggregates:
      - Replies sent within window, total likes, total retweets, average engagement.
      - Scheduled tweet queue activity (sent, pending, cancelled) and persona breakdown.
      - Humor approval rate, total ratings, and top-rated content snippets.
      - Multi-window delta comparisons (current window vs previous period).
      - Operational health scorecard (database, queue throughput, ratings sentiment).
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
        "deltas": {
            "replies": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "likes": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "retweets": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "queue_sent": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
        },
        "health_scorecard": {
            "db_connected": False,
            "queue_backlog": 0,
            "sentiment_status": "Neutral",
            "overall_health": "Healthy",
        },
    }

    try:
        with db.get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            digest["health_scorecard"]["db_connected"] = True

            # 1. Replies & Engagement over current window
            cursor.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(likes), 0), COALESCE(SUM(retweets), 0)
                FROM replied_tweets
                WHERE replied_at >= datetime('now', '-' || ? || ' days')
                """,
                (str(days),),
            )
            rep_row = cursor.fetchone()
            tot_rep, tot_likes, tot_rts = (0, 0, 0)
            if rep_row:
                tot_rep, tot_likes, tot_rts = rep_row
                digest["replies"]["total_replies"] = tot_rep
                digest["replies"]["total_likes"] = tot_likes
                digest["replies"]["total_retweets"] = tot_rts
                if tot_rep > 0:
                    digest["replies"]["avg_likes_per_reply"] = round(tot_likes / tot_rep, 1)
                    digest["replies"]["avg_retweets_per_reply"] = round(tot_rts / tot_rep, 1)

            # Previous period replies & engagement (from -2*days to -days)
            cursor.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(likes), 0), COALESCE(SUM(retweets), 0)
                FROM replied_tweets
                WHERE replied_at < datetime('now', '-' || ? || ' days')
                  AND replied_at >= datetime('now', '-' || ? || ' days')
                """,
                (str(days), str(days * 2)),
            )
            prev_rep_row = cursor.fetchone()
            prev_rep, prev_likes, prev_rts = (0, 0, 0)
            if prev_rep_row:
                prev_rep, prev_likes, prev_rts = prev_rep_row

            digest["deltas"]["replies"] = _compute_delta(tot_rep, prev_rep)
            digest["deltas"]["likes"] = _compute_delta(tot_likes, prev_likes)
            digest["deltas"]["retweets"] = _compute_delta(tot_rts, prev_rts)

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
            cur_sent_queue = 0
            for status, count in cursor.fetchall():
                digest["queue"]["total_scheduled"] += count
                if status in digest["queue"]:
                    digest["queue"][status] = count
                if status == "sent":
                    cur_sent_queue = count

            # Previous period queue sent
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM scheduled_tweets
                WHERE status = 'sent'
                  AND created_at < datetime('now', '-' || ? || ' days')
                  AND created_at >= datetime('now', '-' || ? || ' days')
                """,
                (str(days), str(days * 2)),
            )
            prev_sent_row = cursor.fetchone()
            prev_sent_queue = prev_sent_row[0] if prev_sent_row else 0
            digest["deltas"]["queue_sent"] = _compute_delta(cur_sent_queue, prev_sent_queue)

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

            # 4. Operational Health Scorecard Metrics
            backlog = digest["queue"].get("pending", 0)
            digest["health_scorecard"]["queue_backlog"] = backlog

            approval = digest["ratings"].get("approval_rate", 0.0)
            if digest["ratings"]["total_ratings"] == 0:
                digest["health_scorecard"]["sentiment_status"] = "Neutral (No Data)"
            elif approval >= 70.0:
                digest["health_scorecard"]["sentiment_status"] = "Positive"
            elif approval >= 40.0:
                digest["health_scorecard"]["sentiment_status"] = "Moderate"
            else:
                digest["health_scorecard"]["sentiment_status"] = "Needs Review"

            if backlog > 50:
                digest["health_scorecard"]["overall_health"] = "Degraded (High Queue Backlog)"
            else:
                digest["health_scorecard"]["overall_health"] = "Healthy"

    except Exception as e:
        logger.error(f"Error compiling performance digest: {e}")
        digest["health_scorecard"]["overall_health"] = f"Warning: {e}"

    return digest


def export_digest_markdown(digest):
    """Formats digest statistics into clean Markdown report for operators."""
    rep = digest.get("replies", {})
    queue = digest.get("queue", {})
    rat = digest.get("ratings", {})
    deltas = digest.get("deltas", {})
    scorecard = digest.get("health_scorecard", {})
    top_items = rat.get("top_humor", [])

    if top_items:
        top_humor_md = "\n".join([f"- *\"{item['content']}\"*" for item in top_items])
    else:
        top_humor_md = "- *None recorded yet.*"

    personas_md = ", ".join([f"{k}: {v}" for k, v in queue.get("persona_distribution", {}).items()]) or "None"

    def fmt_delta(key):
        d = deltas.get(key, {})
        diff = d.get("diff", 0)
        pct = d.get("pct", 0.0)
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff} ({sign}{pct}%) vs prior {digest.get('window_days', 7)}d"

    md = f"""# 🚀 Tactful Humor Bot — Weekly Performance Digest
*Generated at: {digest.get('generated_at', 'N/A')} (Window: past {digest.get('window_days', 7)} days)*

## 🩺 System Operational Health Scorecard
- **Overall Status:** {scorecard.get('overall_health', 'Unknown')}
- **Database Connection:** {"Operational" if scorecard.get('db_connected') else "Disconnected"}
- **Pending Queue Backlog:** {scorecard.get('queue_backlog', 0)} items
- **Community Sentiment Rating:** {scorecard.get('sentiment_status', 'Unknown')}

## 📈 Public Replies & Engagement (with Multi-Window Delta Trends)
- **Total Replies Dispatched:** {rep.get('total_replies', 0)} [{fmt_delta('replies')}]
- **Total Likes Accumulated:** {rep.get('total_likes', 0)} (avg {rep.get('avg_likes_per_reply', 0)} / reply)
  - Delta: [{fmt_delta('likes')}]
- **Total Retweets:** {rep.get('total_retweets', 0)} (avg {rep.get('avg_retweets_per_reply', 0)} / reply)
  - Delta: [{fmt_delta('retweets')}]

## 📅 Scheduled Queue Operations
- **Total Scheduled Tweets:** {queue.get('total_scheduled', 0)}
  - Pending: {queue.get('pending', 0)}
  - Dispatched (Sent): {queue.get('sent', 0)} [{fmt_delta('queue_sent')}]
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
