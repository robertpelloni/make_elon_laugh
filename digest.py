"""
Performance Digest Module.

Computes multi-window performance digests across replies, public engagement,
joke approval ratings, automated tweet queuing, and system operational health.
Provides previous-period delta trend comparisons, operational health scorecards,
and exportable markdown and structured summaries for bot operators.
"""

import logging
from datetime import datetime, timezone
import sqlite3
import db

logger = logging.getLogger(__name__)


def evaluate_performance_alerts(digest_data, approval_threshold=40.0, backlog_threshold=50):
    """
    Evaluates automated threshold alerts based on digest metrics.
    Returns a list of alert dicts: [{"level": "warning"|"critical", "type": "...", "message": "..."}].
    """
    alerts = []
    scorecard = digest_data.get("health_scorecard", {})
    rat = digest_data.get("ratings", {})
    queue = digest_data.get("queue", {})

    if not scorecard.get("db_connected", True):
        alerts.append({
            "level": "critical",
            "type": "database_disconnected",
            "message": "Database connection is inactive or unreachable."
        })

    backlog = queue.get("pending", 0)
    if backlog > backlog_threshold:
        alerts.append({
            "level": "warning",
            "type": "queue_backlog_high",
            "message": f"Scheduled tweet backlog has reached {backlog} items (threshold: >{backlog_threshold})."
        })

    tot_ratings = rat.get("total_ratings", 0)
    approval_rate = rat.get("approval_rate", 100.0)
    if tot_ratings >= 5 and approval_rate < approval_threshold:
        alerts.append({
            "level": "warning",
            "type": "low_humor_approval",
            "message": (
                f"Humor approval rating has dropped to {approval_rate}% "
                f"(threshold: <{approval_threshold}% across {tot_ratings} reviews)."
            )
        })

    syn = digest_data.get("syndication", {})
    tot_posts = syn.get("total_posts", 0)
    syn_plats = syn.get("platforms", {})
    tot_syn_engagement = sum(
        p.get("likes", 0) + p.get("shares", 0) for p in syn_plats.values()
    )

    if tot_posts >= 5 and tot_syn_engagement == 0:
        alerts.append({
            "level": "warning",
            "type": "federation_engagement_stall",
            "message": (
                f"Social federation engagement stall detected: {tot_posts} posts "
                "syndicated with 0 total likes or shares."
            )
        })

    return alerts


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
            "top_reply": None,
        },
        "queue": {
            "total_scheduled": 0,
            "pending": 0,
            "sent": 0,
            "cancelled": 0,
            "persona_distribution": {},
            "account_distribution": {},
        },
        "ratings": {
            "total_ratings": 0,
            "upvotes": 0,
            "downvotes": 0,
            "approval_rate": 0.0,
            "top_humor": [],
        },
        "syndication": {
            "total_posts": 0,
            "platforms": {
                "mastodon": {"posts": 0, "likes": 0, "shares": 0},
                "bluesky": {"posts": 0, "likes": 0, "shares": 0}
            }
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
            "sentiment_status": "Neutral (No Data)",
            "federation_health": "Idle",
            "overall_health": "Healthy",
        },
        "alerts": [],
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

                    # Extract top performing reply by combined engagement (likes + retweets)
                    cursor.execute(
                        """
                        SELECT tweet_id, replied_at, likes, retweets
                        FROM replied_tweets
                        WHERE replied_at >= datetime('now', '-' || ? || ' days')
                        ORDER BY (likes + retweets) DESC, replied_at DESC
                        LIMIT 1
                        """,
                        (str(days),),
                    )
                    top_row = cursor.fetchone()
                    if top_row:
                        digest["replies"]["top_reply"] = {
                            "tweet_id": top_row[0],
                            "replied_at": top_row[1],
                            "likes": top_row[2],
                            "retweets": top_row[3],
                        }

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

            # Multi-account distribution in queue
            try:
                cursor.execute(
                    """
                    SELECT COALESCE(account_handle, '@make_elon_laugh'), COUNT(*)
                    FROM scheduled_tweets
                    WHERE created_at >= datetime('now', '-' || ? || ' days')
                    GROUP BY account_handle
                    """,
                    (str(days),),
                )
                for acc, count in cursor.fetchall():
                    digest["queue"]["account_distribution"][acc or "@make_elon_laugh"] = count
            except sqlite3.OperationalError:
                pass

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

            # 4. Syndication Multi-Platform Metrics
            digest["syndication"] = db.get_syndication_summary_metrics(db_path=db_path)

            # 5. Operational Health Scorecard Metrics
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

            syn_posts = digest["syndication"].get("total_posts", 0)
            syn_plats = digest["syndication"].get("platforms", {})
            syn_eng = sum(p.get("likes", 0) + p.get("shares", 0) for p in syn_plats.values())

            if syn_posts >= 5 and syn_eng == 0:
                digest["health_scorecard"]["federation_health"] = "Stalled (No Engagement)"
            elif syn_posts > 0:
                digest["health_scorecard"]["federation_health"] = "Active"
            else:
                digest["health_scorecard"]["federation_health"] = "Idle"

            if backlog > 50:
                digest["health_scorecard"]["overall_health"] = "Degraded (High Queue Backlog)"
            elif digest["health_scorecard"]["federation_health"] == "Stalled (No Engagement)":
                digest["health_scorecard"]["overall_health"] = "Attention (Federation Stalled)"
            else:
                digest["health_scorecard"]["overall_health"] = "Healthy"

            # Evaluate performance threshold alerts
            digest["alerts"] = evaluate_performance_alerts(digest)

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
    alerts = digest.get("alerts", [])

    if top_items:
        top_humor_md = "\n".join([f"- *\"{item['content']}\"*" for item in top_items])
    else:
        top_humor_md = "- *None recorded yet.*"

    personas_md = ", ".join([f"{k}: {v}" for k, v in queue.get("persona_distribution", {}).items()]) or "None"
    accounts_md = ", ".join([f"{k}: {v}" for k, v in queue.get("account_distribution", {}).items()]) or "None"

    def fmt_delta(key):
        d = deltas.get(key, {})
        diff = d.get("diff", 0)
        pct = d.get("pct", 0.0)
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff} ({sign}{pct}%) vs prior {digest.get('window_days', 7)}d"

    syn = digest.get('syndication', {})
    syn_plats = syn.get('platforms', {})
    mast_stats = syn_plats.get('mastodon', {})
    bsky_stats = syn_plats.get('bluesky', {})

    top_rep = rep.get("top_reply")
    if top_rep:
        top_rep_md = f"- **Top Performing Reply:** Tweet ID `{top_rep['tweet_id']}` " \
                     f"({top_rep['likes']} likes, {top_rep['retweets']} retweets, posted {top_rep['replied_at']})"
    else:
        top_rep_md = "- **Top Performing Reply:** None recorded in this period."

    if alerts:
        alerts_md = "## ⚠️ Active System Anomaly Alerts\n" + "\n".join(
            [f"- **[{a.get('level', 'warning').upper()}]** {a.get('message')}" for a in alerts]
        ) + "\n\n"
    else:
        alerts_md = "## ✅ System Alerts\n- *All system parameters within nominal thresholds. No active anomalies.*\n\n"

    mast_posts = mast_stats.get('posts', 0)
    mast_likes = mast_stats.get('likes', 0)
    mast_shares = mast_stats.get('shares', 0)
    mast_avg = round((mast_likes + mast_shares) / mast_posts, 1) if mast_posts > 0 else 0.0

    bsky_posts = bsky_stats.get('posts', 0)
    bsky_likes = bsky_stats.get('likes', 0)
    bsky_shares = bsky_stats.get('shares', 0)
    bsky_avg = round((bsky_likes + bsky_shares) / bsky_posts, 1) if bsky_posts > 0 else 0.0

    md = f"""# 🚀 Tactful Humor Bot — Weekly Performance Digest
*Generated at: {digest.get('generated_at', 'N/A')} (Window: past {digest.get('window_days', 7)} days)*

{alerts_md}## 🩺 System Operational Health Scorecard
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
{top_rep_md}

## 📅 Scheduled Queue Operations
- **Total Scheduled Tweets:** {queue.get('total_scheduled', 0)}
  - Pending: {queue.get('pending', 0)}
  - Dispatched (Sent): {queue.get('sent', 0)} [{fmt_delta('queue_sent')}]
  - Cancelled: {queue.get('cancelled', 0)}
- **Persona Distribution:** {personas_md}
- **Account Attribution:** {accounts_md}

## 🌟 Humor Approval & Ratings
- **Total Community Ratings:** {rat.get('total_ratings', 0)}
- **Humor Approval Rate:** {rat.get('approval_rate', 0)}% (+{rat.get('upvotes', 0)} / -{rat.get('downvotes', 0)})

### Top Rated Humor Snippets
{top_humor_md}

## 🌐 Social Federation Multi-Platform Reach
- **Total Syndicated Posts:** {syn.get('total_posts', 0)}
- **Mastodon ActivityPub:** {mast_posts} posts ({mast_likes} favs, {mast_shares} shares, avg {mast_avg}/post)
- **Bluesky ATProto:** {bsky_posts} posts ({bsky_likes} likes, {bsky_shares} reposts, avg {bsky_avg}/post)

---
*Autonomous Tactful Humor Operations Console*
"""
    return md


def export_digest_html(digest):
    """
    Formats digest statistics into a standalone, styled HTML report
    suitable for email delivery, static archiving, or browser review.
    """
    rep = digest.get("replies", {})
    queue = digest.get("queue", {})
    rat = digest.get("ratings", {})
    deltas = digest.get("deltas", {})
    scorecard = digest.get("health_scorecard", {})
    top_items = rat.get("top_humor", [])
    syn = digest.get("syndication", {})
    syn_plats = syn.get("platforms", {})
    mast_stats = syn_plats.get("mastodon", {})
    bsky_stats = syn_plats.get("bluesky", {})
    alerts = digest.get("alerts", [])

    top_humor_html = "".join([f"<li><em>&ldquo;{item.get('content', '')}&rdquo;</em></li>" for item in top_items])
    if not top_humor_html:
        top_humor_html = "<li><em>None recorded yet.</em></li>"

    top_rep = rep.get("top_reply")
    if top_rep:
        top_rep_html = (
            f'<div class="card" style="margin-top: 12px; border-left: 4px solid #0284c7;">'
            f'<div class="card-title">Top Performing Reply</div>'
            f'<div style="font-size: 0.95rem; font-weight: 600;">Tweet ID: <code>{top_rep["tweet_id"]}</code></div>'
            f'<div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">'
            f'{top_rep["likes"]} likes &bull; {top_rep["retweets"]} retweets &bull; Posted {top_rep["replied_at"]}'
            f'</div></div>'
        )
    else:
        top_rep_html = ""

    personas_dict = queue.get("persona_distribution", {})
    if personas_dict:
        persona_badges = "".join([
            f'<span class="badge" style="margin-right: 6px; margin-bottom: 4px;">{p}: {cnt}</span>'
            for p, cnt in personas_dict.items()
        ])
    else:
        persona_badges = '<span style="color: #94a3b8; font-size: 0.85rem;">None</span>'

    accounts_dict = queue.get("account_distribution", {})
    if accounts_dict:
        account_badges = "".join([
            f'<span class="badge" style="margin-right: 6px; margin-bottom: 4px; '
            f'background: #e0e7ff; color: #3730a3;">{a}: {cnt}</span>'
            for a, cnt in accounts_dict.items()
        ])
    else:
        account_badges = '<span style="color: #94a3b8; font-size: 0.85rem;">None</span>'

    if alerts:
        alert_items = "".join([
            f'<li style="margin-bottom: 4px;"><strong>[{a.get("level", "warning").upper()}]</strong> '
            f'{a.get("message")}</li>'
            for a in alerts
        ])
        alerts_banner = f"""
    <div style="background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #ef4444;
                border-radius: 8px; padding: 14px; margin-bottom: 20px;">
      <h3 style="color: #991b1b; margin: 0 0 8px 0; font-size: 1rem;">
        ⚠️ Active System Anomaly Alerts ({len(alerts)})
      </h3>
      <ul style="margin: 0; padding-left: 20px; color: #7f1d1d;">
        {alert_items}
      </ul>
    </div>
"""
    else:
        alerts_banner = """
    <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #10b981;
                border-radius: 8px; padding: 12px; margin-bottom: 20px;">
      <span style="color: #166534; font-weight: 600; font-size: 0.9rem;">✅ System Status Nominal:</span>
      <span style="color: #15803d; font-size: 0.85rem;">All operational parameters within expected thresholds.</span>
    </div>
"""

    def fmt_delta(key):
        d = deltas.get(key, {})
        diff = d.get("diff", 0)
        pct = d.get("pct", 0.0)
        sign = "+" if diff > 0 else ""
        color = "#10b981" if diff >= 0 else "#ef4444"
        return f'<span style="color: {color}; font-weight: bold;">{sign}{diff} ({sign}{pct}%)</span>'

    mast_posts = mast_stats.get('posts', 0)
    mast_likes = mast_stats.get('likes', 0)
    mast_shares = mast_stats.get('shares', 0)
    mast_avg = round((mast_likes + mast_shares) / mast_posts, 1) if mast_posts > 0 else 0.0

    bsky_posts = bsky_stats.get('posts', 0)
    bsky_likes = bsky_stats.get('likes', 0)
    bsky_shares = bsky_stats.get('shares', 0)
    bsky_avg = round((bsky_likes + bsky_shares) / bsky_posts, 1) if bsky_posts > 0 else 0.0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Tactful Humor Bot — Performance Digest</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #1e293b;
      background-color: #f8fafc;
      margin: 0;
      padding: 30px;
    }}
    .container {{
      max-width: 760px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }}
    h1 {{ color: #0284c7; margin-top: 0; border-bottom: 2px solid #e0f2fe; padding-bottom: 12px; }}
    h2 {{
      color: #334155;
      margin-top: 24px;
      font-size: 1.25rem;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 6px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      font-size: 0.85rem;
      font-weight: 600;
      border-radius: 9999px;
      background: #e0f2fe;
      color: #0369a1;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin: 16px 0;
    }}
    .card {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 16px;
    }}
    .card-title {{ font-size: 0.85rem; color: #64748b; margin-bottom: 4px; }}
    .card-val {{ font-size: 1.5rem; font-weight: bold; color: #0f172a; }}
    ul {{ padding-left: 20px; }}
    li {{ margin-bottom: 6px; }}
    footer {{ margin-top: 32px; font-size: 0.8rem; color: #94a3b8; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>🚀 Tactful Humor Bot — Performance Digest</h1>
    <p style="margin-bottom: 20px;">
      <strong>Window:</strong> Past {digest.get('window_days', 7)} days &bull;
      <strong>Generated:</strong> {digest.get('generated_at', 'N/A')}
    </p>

    {alerts_banner}

    <h2>🩺 System Operational Health</h2>
    <div class="grid">
      <div class="card">
        <div class="card-title">Overall Status</div>
        <div class="card-val">{scorecard.get('overall_health', 'Unknown')}</div>
      </div>
      <div class="card">
        <div class="card-title">Database Status</div>
        <div class="card-val">{"Connected" if scorecard.get('db_connected') else "Disconnected"}</div>
      </div>
      <div class="card">
        <div class="card-title">Queue Backlog</div>
        <div class="card-val">{scorecard.get('queue_backlog', 0)}</div>
      </div>
    </div>

    <h2>📈 Public Replies &amp; Engagement Deltas</h2>
    <div class="grid">
      <div class="card">
        <div class="card-title">Total Replies</div>
        <div class="card-val">{rep.get('total_replies', 0)}</div>
        <div>{fmt_delta('replies')}</div>
      </div>
      <div class="card">
        <div class="card-title">Total Likes</div>
        <div class="card-val">{rep.get('total_likes', 0)}</div>
        <div>{fmt_delta('likes')}</div>
      </div>
      <div class="card">
        <div class="card-title">Total Retweets</div>
        <div class="card-val">{rep.get('total_retweets', 0)}</div>
        <div>{fmt_delta('retweets')}</div>
      </div>
    </div>
    {top_rep_html}

    <h2>📅 Scheduled Queue Operations</h2>
    <ul>
      <li><strong>Total Scheduled:</strong> {queue.get('total_scheduled', 0)}</li>
      <li><strong>Dispatched (Sent):</strong> {queue.get('sent', 0)} ({fmt_delta('queue_sent')})</li>
      <li><strong>Pending Backlog:</strong> {queue.get('pending', 0)}</li>
      <li><strong>Cancelled:</strong> {queue.get('cancelled', 0)}</li>
      <li><strong>Persona Distribution:</strong> {persona_badges}</li>
      <li><strong>Account Attribution:</strong> {account_badges}</li>
    </ul>

    <h2>🌟 Community Humor Approval</h2>
    <p><strong>Approval Rating:</strong> {rat.get('approval_rate', 0)}%
       (+{rat.get('upvotes', 0)} / -{rat.get('downvotes', 0)} across {rat.get('total_ratings', 0)} votes)</p>
    <ul>
      {top_humor_html}
    </ul>

    <h2>🌐 Social Federation Reach</h2>
    <ul>
      <li><strong>Total Syndicated Posts:</strong> {syn.get('total_posts', 0)}</li>
      <li><strong>Mastodon:</strong> {mast_posts} posts &bull;
          {mast_likes} favs &bull; {mast_shares} reblogs &bull; avg {mast_avg}/post</li>
      <li><strong>Bluesky:</strong> {bsky_posts} posts &bull;
          {bsky_likes} likes &bull; {bsky_shares} reposts &bull; avg {bsky_avg}/post</li>
    </ul>

    <footer>
      Autonomous Tactful Humor Operations Console &bull; Confidential Digest Report
    </footer>
  </div>
</body>
</html>"""
    return html
