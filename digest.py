"""
Performance Digest Module.

Computes multi-window performance digests across replies, public engagement,
joke approval ratings, automated tweet queuing, and system operational health.
Provides previous-period delta trend comparisons, operational health scorecards,
and exportable markdown and structured summaries for bot operators.
"""

import logging
from datetime import datetime, timezone, timedelta
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

    dlq = digest_data.get("dlq", {})
    dlq_exhausted = dlq.get("exhausted", 0)
    dlq_pending = dlq.get("pending", 0)

    if dlq_exhausted > 0:
        alerts.append({
            "level": "critical",
            "type": "syndication_dlq_exhausted_failures",
            "message": f"Syndication DLQ has {dlq_exhausted} exhausted broadcast failures requiring manual review."
        })
    elif dlq_pending > 5:
        alerts.append({
            "level": "warning",
            "type": "syndication_dlq_pending_high",
            "message": f"Syndication DLQ pending retries elevated ({dlq_pending} pending retries)."
        })

    cb_data = digest_data.get("circuit_breakers", {})
    cb_list = list(cb_data.values()) if isinstance(cb_data, dict) else (cb_data or [])
    for cb in cb_list:
        if not isinstance(cb, dict):
            continue
        plat = cb.get("platform", "unknown").capitalize()
        state = cb.get("state", "CLOSED").upper()
        if state == "OPEN":
            reason = cb.get("last_failure_reason", "Outage")
            alerts.append({
                "level": "critical",
                "type": f"circuit_breaker_{cb.get('platform')}_open",
                "message": f"Federation circuit breaker for {plat} is OPEN ({reason}). Broadcasts are failing fast."
            })
        elif state == "HALF-OPEN":
            alerts.append({
                "level": "warning",
                "type": f"circuit_breaker_{cb.get('platform')}_half_open",
                "message": f"Federation circuit breaker for {plat} is HALF-OPEN. Probing for network recovery."
            })

    # Per-platform divergence alerts
    platform_breakdowns = extract_per_platform_metric_breakdowns(digest_data)
    for p_name, p_data in platform_breakdowns.items():
        if p_data.get("posts", 0) >= 3 and p_data.get("total_engagement", 0) == 0:
            alerts.append({
                "level": "warning",
                "type": f"platform_divergence_{p_name}",
                "message": (
                    f"Platform divergence on {p_name.capitalize()}: {p_data.get('posts')} posts published "
                    "with 0 engagement recorded."
                )
            })

    return alerts


def extract_per_platform_metric_breakdowns(digest_data):
    """
    Extracts structured per-network engagement velocities and distribution shares
    for Twitter/X, Mastodon, Bluesky, and any dynamically discovered federation network.

    Returns dict mapping platform name to:
      - 'posts': post count
      - 'likes': total likes
      - 'shares': total shares/retweets
      - 'total_engagement': likes + shares
      - 'avg_engagement_per_post': engagement velocity
      - 'velocity_tier': 'High' | 'Moderate' | 'Low' | 'Stalled'
      - 'share_of_total_posts_pct': percentage of total bot dispatches across all networks
    """
    platforms = {}
    rep = digest_data.get("replies", {})
    tw_posts = rep.get("total_replies", 0)
    tw_likes = rep.get("total_likes", 0)
    tw_shares = rep.get("total_retweets", 0)
    tw_eng = tw_likes + tw_shares
    tw_avg = round(tw_eng / tw_posts, 2) if tw_posts > 0 else 0.0

    def _calc_tier(avg_val, post_cnt, eng_cnt):
        if avg_val >= 5.0:
            return "High"
        if avg_val >= 1.0:
            return "Moderate"
        if post_cnt >= 3 and eng_cnt == 0:
            return "Stalled"
        return "Low"

    platforms["twitter"] = {
        "platform": "twitter",
        "display_name": "Twitter / X",
        "posts": tw_posts,
        "likes": tw_likes,
        "shares": tw_shares,
        "total_engagement": tw_eng,
        "avg_engagement_per_post": tw_avg,
        "velocity_tier": _calc_tier(tw_avg, tw_posts, tw_eng),
        "share_of_total_posts_pct": 0.0,
    }

    syn = digest_data.get("syndication", {})
    syn_plats = syn.get("platforms", {})
    for plat_name, p_stats in syn_plats.items():
        p_posts = p_stats.get("posts", 0)
        p_likes = p_stats.get("likes", 0)
        p_shares = p_stats.get("shares", 0)
        p_eng = p_likes + p_shares
        p_avg = round(p_eng / p_posts, 2) if p_posts > 0 else 0.0
        v_tier = _calc_tier(p_avg, p_posts, p_eng)

        platforms[plat_name] = {
            "platform": plat_name,
            "display_name": plat_name.capitalize(),
            "posts": p_posts,
            "likes": p_likes,
            "shares": p_shares,
            "total_engagement": p_eng,
            "avg_engagement_per_post": p_avg,
            "velocity_tier": v_tier,
            "share_of_total_posts_pct": 0.0,
        }

    total_all_posts = sum(p["posts"] for p in platforms.values())
    if total_all_posts > 0:
        for p in platforms.values():
            p["share_of_total_posts_pct"] = round((p["posts"] / total_all_posts) * 100.0, 1)

    return platforms


def _compute_delta(current, previous):
    """Computes difference and percentage change between two numeric values."""
    diff = current - previous
    if previous > 0:
        pct = round((diff / previous) * 100, 1)
    else:
        pct = 100.0 if current > 0 else 0.0
    return {"current": current, "previous": previous, "diff": diff, "pct": pct}


def compute_hourly_engagement_heatmap(days=30, db_path=db.DB_PATH):
    """
    Computes hourly engagement distribution (0-23 UTC) across public replies and
    syndicated federation posts over the specified historical window (default 30 days).

    Returns dictionary with:
      - 'hours': list of 24 hourly dicts (hour, posts, likes, shares, total_engagement)
      - 'peak_hour': the hour with maximum total engagement (or post density)
      - 'peak_window_label': e.g. '14:00 - 15:00 UTC'
      - 'total_tracked_events': total posts/replies sampled across the window
    """
    db.init_db(db_path)
    heatmap = {
        h: {"hour": h, "posts": 0, "likes": 0, "shares": 0, "total_engagement": 0}
        for h in range(24)
    }
    total_events = 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        # Sample replied_tweets within window
        cursor.execute("""
            SELECT replied_at, likes, retweets
            FROM replied_tweets
            WHERE replied_at >= ?
        """, (cutoff,))
        for replied_at, l, rt in cursor.fetchall():
            if not replied_at:
                continue
            try:
                clean_ts = str(replied_at).replace("Z", "").split("+")[0].strip()
                if " " in clean_ts:
                    hr = int(clean_ts.split(" ")[1].split(":")[0])
                elif "T" in clean_ts:
                    hr = int(clean_ts.split("T")[1].split(":")[0])
                else:
                    continue
                if 0 <= hr < 24:
                    heatmap[hr]["posts"] += 1
                    heatmap[hr]["likes"] += (l or 0)
                    heatmap[hr]["shares"] += (rt or 0)
                    heatmap[hr]["total_engagement"] += (l or 0) + (rt or 0)
                    total_events += 1
            except Exception:
                continue

        # Sample syndicated_posts within window
        cursor.execute("""
            SELECT created_at, likes, shares
            FROM syndicated_posts
            WHERE created_at >= ?
        """, (cutoff,))
        for created_at, l, sh in cursor.fetchall():
            if not created_at:
                continue
            try:
                clean_ts = str(created_at).replace("Z", "").split("+")[0].strip()
                if " " in clean_ts:
                    hr = int(clean_ts.split(" ")[1].split(":")[0])
                elif "T" in clean_ts:
                    hr = int(clean_ts.split("T")[1].split(":")[0])
                else:
                    continue
                if 0 <= hr < 24:
                    heatmap[hr]["posts"] += 1
                    heatmap[hr]["likes"] += (l or 0)
                    heatmap[hr]["shares"] += (sh or 0)
                    heatmap[hr]["total_engagement"] += (l or 0) + (sh or 0)
                    total_events += 1
            except Exception:
                continue

        conn.close()
    except Exception as e:
        logger.warning(f"Error computing hourly engagement heatmap: {e}")

    hours_list = [heatmap[h] for h in range(24)]
    if total_events > 0:
        peak_entry = max(hours_list, key=lambda x: (x["total_engagement"], x["posts"]))
        peak_h = peak_entry["hour"]
    else:
        # Fallback to industry peak 17:00 UTC
        peak_h = 17
        peak_entry = heatmap[peak_h]

    return {
        "hours": hours_list,
        "peak_hour": peak_h,
        "peak_window_label": f"{peak_h:02d}:00 - {(peak_h + 1) % 24:02d}:00 UTC",
        "peak_engagement": peak_entry["total_engagement"],
        "peak_posts": peak_entry["posts"],
        "total_tracked_events": total_events,
    }


def generate_digest_engagement_recommendations(digest_data):
    """
    Synthesizes actionable audience engagement recommendations from digest performance metrics,
    heatmap peak windows, persona distribution, and federation health.
    """
    recs = []
    heatmap = digest_data.get("heatmap", {})
    peak_label = heatmap.get("peak_window_label", "17:00 - 18:00 UTC")
    total_events = heatmap.get("total_tracked_events", 0)

    if total_events > 0:
        recs.append(
            f"🎯 Optimal Post Timing: Highest historical audience engagement converges at "
            f"{peak_label} ({heatmap.get('peak_engagement', 0)} engagements across "
            f"{heatmap.get('peak_posts', 0)} posts). Schedule high-priority announcements in this slot."
        )
    else:
        recs.append(
            f"🎯 Recommended Post Timing: Defaulting to high-traffic aerospace window {peak_label}. "
            "Queue posts across this timeframe to seed historical telemetry."
        )

    queue = digest_data.get("queue", {})
    persona_dist = queue.get("persona_distribution", {})
    if persona_dist:
        top_persona = max(persona_dist.items(), key=lambda kv: kv[1])[0]
        recs.append(
            f"🎭 Content Persona Allocation: '{top_persona}' leads queue volume ({persona_dist[top_persona]} posts). "
            "Consider rotating with secondary personas to preserve audience freshness."
        )

    media_dist = queue.get("media_distribution", {})
    comp_count = media_dist.get("composite", 0)
    single_count = media_dist.get("single", 0)
    if single_count > 0 and comp_count == 0:
        recs.append(
            "🌌 Media Diversity: 100% of queued media are single cards. Integrate multi-panel composite infographics "
            "to lift deep-space narrative engagement across Mastodon and Bluesky."
        )

    cbs = digest_data.get("circuit_breakers", [])
    cb_vals = list(cbs.values()) if isinstance(cbs, dict) else (cbs or [])
    open_cbs = [c for c in cb_vals if isinstance(c, dict) and c.get("state") == "OPEN"]
    if open_cbs:
        c_names = ", ".join([c.get("platform", "").capitalize() for c in open_cbs])
        recs.append(
            f"⚠️ Operational Resilience: Outage detected on {c_names} (Circuit OPEN). "
            "Wait for automatic canary recovery or verify upstream node connectivity."
        )

    rat = digest_data.get("ratings", {})
    approval = rat.get("approval_rate", 0.0)
    total_ratings = rat.get("total_ratings", 0)
    if total_ratings >= 5 and approval < 60.0:
        recs.append(
            f"📉 Humor Calibration: Approval rating at {approval:.1f}%. "
            "Refine LLM tone styling or switch persona presets in Command Center."
        )
    elif approval >= 80.0 and total_ratings >= 5:
        recs.append(
            f"🌟 Strong Audience Alignment: High community approval ({approval:.1f}%). "
            "Maintain current humor prompt parameters."
        )

    return recs


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
            "media_distribution": {
                "single": 0,
                "composite": 0,
            },
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
        "dlq": {
            "total": 0,
            "pending": 0,
            "exhausted": 0,
            "replayed": 0,
            "discarded": 0
        },
        "circuit_breakers": [],
        "platform_breakdowns": {},
        "heatmap": {},
        "recommendations": [],
        "deltas": {
            "replies": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "likes": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "retweets": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "queue_sent": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "syndication_posts": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
            "syndication_engagement": {"current": 0, "previous": 0, "diff": 0, "pct": 0.0},
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

            # Media distribution in queue (single card vs composite infographic)
            try:
                cursor.execute(
                    """
                    SELECT COALESCE(media_type, 'single'), COUNT(*)
                    FROM scheduled_tweets
                    WHERE created_at >= datetime('now', '-' || ? || ' days')
                    GROUP BY media_type
                    """,
                    (str(days),),
                )
                for m_type, count in cursor.fetchall():
                    norm_type = m_type if m_type in ("single", "composite") else "single"
                    digest["queue"]["media_distribution"][norm_type] = count
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

            # 4. Syndication Multi-Platform Metrics (Windowed & Delta Trends)
            digest["syndication"] = db.get_syndication_summary_metrics(days=days, db_path=db_path)
            prev_syndication = db.get_syndication_summary_metrics(days=days * 2, start_days_ago=days, db_path=db_path)

            cur_syn_posts = digest["syndication"].get("total_posts", 0)
            prev_syn_posts = prev_syndication.get("total_posts", 0)
            digest["deltas"]["syndication_posts"] = _compute_delta(cur_syn_posts, prev_syn_posts)

            cur_syn_eng = sum(
                p.get("likes", 0) + p.get("shares", 0)
                for p in digest["syndication"].get("platforms", {}).values()
            )
            prev_syn_eng = sum(
                p.get("likes", 0) + p.get("shares", 0)
                for p in prev_syndication.get("platforms", {}).values()
            )
            digest["deltas"]["syndication_engagement"] = _compute_delta(cur_syn_eng, prev_syn_eng)

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

            # 6. Dead-Letter Queue & Circuit Breakers Telemetry Aggregation
            digest["dlq"] = db.get_syndication_dlq_metrics(db_path=db_path)
            digest["circuit_breakers"] = db.get_all_circuit_breakers(db_path=db_path)
            raw_cbs = digest["circuit_breakers"]
            cb_vals = list(raw_cbs.values()) if isinstance(raw_cbs, dict) else raw_cbs

            open_cbs = [cb for cb in cb_vals if isinstance(cb, dict) and cb.get("state") == "OPEN"]
            half_open_cbs = [cb for cb in cb_vals if isinstance(cb, dict) and cb.get("state") == "HALF-OPEN"]

            if open_cbs:
                open_plats = ", ".join([c.get("platform", "").capitalize() for c in open_cbs])
                digest["health_scorecard"]["federation_health"] = f"Outage ({open_plats} Circuit OPEN)"
            elif half_open_cbs:
                half_plats = ", ".join([c.get("platform", "").capitalize() for c in half_open_cbs])
                digest["health_scorecard"]["federation_health"] = f"Canary Recovery ({half_plats} HALF-OPEN)"
            elif syn_posts >= 5 and syn_eng == 0:
                digest["health_scorecard"]["federation_health"] = "Stalled (No Engagement)"
            elif syn_posts > 0:
                digest["health_scorecard"]["federation_health"] = "Active"
            else:
                digest["health_scorecard"]["federation_health"] = "Idle"

            if open_cbs:
                digest["health_scorecard"]["overall_health"] = "Critical (Federation Outage / Circuit OPEN)"
            elif backlog > 50:
                digest["health_scorecard"]["overall_health"] = "Degraded (High Queue Backlog)"
            elif digest["dlq"].get("exhausted", 0) > 0:
                digest["health_scorecard"]["overall_health"] = "Attention (Syndication Failures in DLQ)"
            elif digest["health_scorecard"]["federation_health"] == "Stalled (No Engagement)":
                digest["health_scorecard"]["overall_health"] = "Attention (Federation Stalled)"
            else:
                digest["health_scorecard"]["overall_health"] = "Healthy"

            # 7. Hourly Heatmap & AI Engagement Recommendations
            digest["heatmap"] = compute_hourly_engagement_heatmap(days=max(days, 30), db_path=db_path)
            digest["recommendations"] = generate_digest_engagement_recommendations(digest)

            # 8. Per-Platform Metric Breakdowns
            digest["platform_breakdowns"] = extract_per_platform_metric_breakdowns(digest)

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
    media_dict = queue.get("media_distribution", {})
    media_md = f"Single: {media_dict.get('single', 0)}, Composite: {media_dict.get('composite', 0)}"

    def fmt_delta(key):
        d = deltas.get(key, {})
        diff = d.get("diff", 0)
        pct = d.get("pct", 0.0)
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff} ({sign}{pct}%) vs prior {digest.get('window_days', 7)}d"

    syn = digest.get('syndication', {})
    syn_plats = syn.get('platforms', {})

    top_rep = rep.get("top_reply")
    if top_rep:
        top_rep_md = f"- **Top Performing Reply:** Tweet ID `{top_rep['tweet_id']}` " \
                     f"({top_rep['likes']} likes, {top_rep['retweets']} retweets, posted {top_rep['replied_at']})"
    else:
        top_rep_md = "- **Top Performing Reply:** None recorded in this period."

    recs = digest.get("recommendations", [])
    if recs:
        recs_md = "## 💡 Strategic Engagement Recommendations\n" + "\n".join(
            [f"- {r}" for r in recs]
        ) + "\n\n"
    else:
        recs_md = ""

    heatmap = digest.get("heatmap", {})
    peak_win = heatmap.get("peak_window_label", "17:00 - 18:00 UTC")
    heatmap_md = f"## ⏱️ Hourly Activity & Optimal Engagement Windows\n" \
                 f"- **Peak Historical Window:** `{peak_win}` " \
                 f"({heatmap.get('peak_engagement', 0)} engagements, {heatmap.get('peak_posts', 0)} posts sampled)\n" \
                 f"- **Total Tracked Historical Dispatches:** {heatmap.get('total_tracked_events', 0)}\n\n"

    if alerts:
        alerts_md = "## ⚠️ Active System Anomaly Alerts\n" + "\n".join(
            [f"- **[{a.get('level', 'warning').upper()}]** {a.get('message')}" for a in alerts]
        ) + "\n\n"
    else:
        alerts_md = "## ✅ System Alerts\n- *All system parameters within nominal thresholds. No active anomalies.*\n\n"

    # Dynamically generate platform reach lines for any discovered platform
    platform_reach_lines = []
    for plat_name, pstats in sorted(syn_plats.items()):
        p_posts = pstats.get('posts', 0)
        p_likes = pstats.get('likes', 0)
        p_shares = pstats.get('shares', 0)
        p_avg = round((p_likes + p_shares) / p_posts, 1) if p_posts > 0 else 0.0
        display_name = plat_name.capitalize()
        platform_reach_lines.append(
            f"- **{display_name}:** {p_posts} posts ({p_likes} likes/favs, {p_shares} shares, avg {p_avg}/post)"
        )

    if not platform_reach_lines:
        platform_reach_lines.append("- *No federated syndication activity recorded.*")

    federation_reach_md = "\n".join(platform_reach_lines)

    pb = digest.get("platform_breakdowns", {})
    if pb:
        pb_lines = []
        for p_key, p_info in sorted(pb.items()):
            p_name = p_info.get("display_name", p_key.capitalize())
            p_velocity = p_info.get("avg_engagement_per_post", 0.0)
            p_tier = p_info.get("velocity_tier", "Low")
            p_share = p_info.get("share_of_total_posts_pct", 0.0)
            pb_lines.append(
                f"- **{p_name}:** Velocity: `{p_velocity}` eng/post (Tier: **{p_tier}**), "
                f"Share of Broadcasts: **{p_share}%**"
            )
        platform_breakdowns_md = "## ⚡ Per-Platform Engagement Velocity & Distribution Share\n" + \
                                 "\n".join(pb_lines) + "\n\n"
    else:
        platform_breakdowns_md = ""

    cbs = digest.get("circuit_breakers", {})
    cb_list = list(cbs.values()) if isinstance(cbs, dict) else (cbs or [])
    if cb_list:
        cb_lines = []
        for cb in cb_list:
            if not isinstance(cb, dict):
                continue
            p = cb.get("platform", "unknown").capitalize()
            st = cb.get("state", "CLOSED").upper()
            fails = cb.get("consecutive_failures", 0)
            thresh = cb.get("failure_threshold", 3)
            icon = "🟢" if st == "CLOSED" else ("🔴" if st == "OPEN" else "🟡")
            reason_str = ""
            if cb.get('last_failure_reason') and st != "CLOSED":
                reason_str = f" - Reason: {cb.get('last_failure_reason')}"
            cb_lines.append(f"- **{icon} {p}:** State `{st}` (Failures: {fails}/{thresh}){reason_str}")
        circuit_breakers_md = "\n".join(cb_lines)
    else:
        circuit_breakers_md = "- *No circuit breaker records found (all nominal).*"

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
- **Media Distribution:** {media_md}

## 🌟 Humor Approval & Ratings
- **Total Community Ratings:** {rat.get('total_ratings', 0)}
- **Humor Approval Rate:** {rat.get('approval_rate', 0)}% (+{rat.get('upvotes', 0)} / -{rat.get('downvotes', 0)})

### Top Rated Humor Snippets
{top_humor_md}

## 🌐 Social Federation Multi-Platform Reach
- **Total Syndicated Posts:** {syn.get('total_posts', 0)} [{fmt_delta('syndication_posts')}]
- **Federated Engagement Delta:** [{fmt_delta('syndication_engagement')}]
{federation_reach_md}

## 🔁 Federation Deliverability & Dead-Letter Queue
- **DLQ Pending Retries:** {digest.get('dlq', {}).get('pending', 0)}
- **DLQ Exhausted Failures:** {digest.get('dlq', {}).get('exhausted', 0)}
- **DLQ Successfully Replayed:** {digest.get('dlq', {}).get('replayed', 0)}
- **DLQ Discarded:** {digest.get('dlq', {}).get('discarded', 0)}

## 🛡️ Federation Circuit Breaker Telemetry
{circuit_breakers_md}

{platform_breakdowns_md}{heatmap_md}{recs_md}---
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

    media_dist = queue.get("media_distribution", {})
    single_cnt = media_dist.get("single", 0)
    comp_cnt = media_dist.get("composite", 0)
    media_badges = (
        f'<span class="badge" style="margin-right: 6px; margin-bottom: 4px; '
        f'background: #fef3c7; color: #92400e;">Single: {single_cnt}</span>'
        f'<span class="badge" style="margin-right: 6px; margin-bottom: 4px; '
        f'background: #ede9fe; color: #5b21b6;">Composite: {comp_cnt}</span>'
    )

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

    html_platform_list = []
    for p, s in sorted(syn_plats.items()):
        p_posts = s.get('posts', 0)
        p_likes = s.get('likes', 0)
        p_shares = s.get('shares', 0)
        p_avg = round((p_likes + p_shares) / p_posts, 1) if p_posts > 0 else 0.0
        html_platform_list.append(
            f"<li><strong>{p.capitalize()}:</strong> {p_posts} posts &bull; "
            f"{p_likes} likes/favs &bull; {p_shares} shares &bull; avg {p_avg}/post</li>"
        )
    federation_html_items = "".join(html_platform_list) or "<li><em>No federated activity recorded.</em></li>"

    cbs = digest.get("circuit_breakers", {})
    cb_list = list(cbs.values()) if isinstance(cbs, dict) else (cbs or [])
    if cb_list:
        cb_html_list = []
        for cb in cb_list:
            if not isinstance(cb, dict):
                continue
            p = cb.get("platform", "unknown").capitalize()
            st = cb.get("state", "CLOSED").upper()
            fails = cb.get("consecutive_failures", 0)
            thresh = cb.get("failure_threshold", 3)
            bg = "#dcfce7" if st == "CLOSED" else ("#fee2e2" if st == "OPEN" else "#fef3c7")
            fg = "#166534" if st == "CLOSED" else ("#991b1b" if st == "OPEN" else "#92400e")
            reason_info = ""
            if cb.get('last_failure_reason') and st != "CLOSED":
                reason_info = f" &bull; <em>{cb.get('last_failure_reason')}</em>"
            cb_html_list.append(
                f'<li><strong>{p}:</strong> <span class="badge" style="background: {bg}; color: {fg};">{st}</span> '
                f'({fails}/{thresh} failures){reason_info}</li>'
            )
        cb_html_items = "".join(cb_html_list)
    else:
        cb_html_items = "<li><em>All circuits nominal (no faults logged).</em></li>"

    recs = digest.get("recommendations", [])
    if recs:
        recs_html_items = "".join([f"<li>{r}</li>" for r in recs])
        recs_section_html = f"""
    <h2>💡 Strategic Engagement Recommendations</h2>
    <div class="card" style="border-left: 4px solid #0284c7; background: #f0f9ff;">
      <ul style="margin: 0; padding-left: 20px;">
        {recs_html_items}
      </ul>
    </div>
"""
    else:
        recs_section_html = ""

    heatmap = digest.get("heatmap", {})
    peak_win = heatmap.get("peak_window_label", "17:00 - 18:00 UTC")
    heatmap_section_html = f"""
    <h2>⏱️ Hourly Engagement & Optimal Windows</h2>
    <div class="card">
      <div style="font-size: 0.95rem; margin-bottom: 8px;">
        <strong>Peak Historical Window:</strong>
        <span class="badge" style="background: #e0f2fe; color: #0369a1;">{peak_win}</span>
        ({heatmap.get('peak_engagement', 0)} engagements sampled across {heatmap.get('peak_posts', 0)} posts)
      </div>
      <div style="font-size: 0.85rem; color: #64748b;">
        Total historical dispatches tracked: <strong>{heatmap.get('total_tracked_events', 0)}</strong>
      </div>
    </div>
"""

    pb = digest.get("platform_breakdowns", {})
    if pb:
        pb_html_rows = []
        for p_key, p_info in sorted(pb.items()):
            p_name = p_info.get("display_name", p_key.capitalize())
            p_vel = p_info.get("avg_engagement_per_post", 0.0)
            p_tier = p_info.get("velocity_tier", "Low")
            p_share = p_info.get("share_of_total_posts_pct", 0.0)
            tier_badge = f'<span class="badge" style="background: #e0e7ff; color: #4338ca;">{p_tier}</span>'
            pb_html_rows.append(f"""
        <tr>
          <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;"><strong>{p_name}</strong></td>
          <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">{p_info.get('posts', 0)}</td>
          <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">{p_vel} / post</td>
          <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">{tier_badge}</td>
          <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0;">{p_share}%</td>
        </tr>
""")
        pb_section_html = f"""
    <h2>⚡ Per-Platform Velocity &amp; Distribution</h2>
    <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-top: 10px;">
      <thead>
        <tr style="background: #f1f5f9; text-align: left; color: #475569;">
          <th style="padding: 8px 12px;">Platform</th>
          <th style="padding: 8px 12px;">Posts</th>
          <th style="padding: 8px 12px;">Velocity</th>
          <th style="padding: 8px 12px;">Tier</th>
          <th style="padding: 8px 12px;">Share</th>
        </tr>
      </thead>
      <tbody>
        {"".join(pb_html_rows)}
      </tbody>
    </table>
"""
    else:
        pb_section_html = ""

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
      <li><strong>Media Distribution:</strong> {media_badges}</li>
    </ul>

    <h2>🌟 Community Humor Approval</h2>
    <p><strong>Approval Rating:</strong> {rat.get('approval_rate', 0)}%
       (+{rat.get('upvotes', 0)} / -{rat.get('downvotes', 0)} across {rat.get('total_ratings', 0)} votes)</p>
    <ul>
      {top_humor_html}
    </ul>

    <h2>🌐 Social Federation Reach</h2>
    <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 8px;">
      Total Posts: <strong>{syn.get('total_posts', 0)}</strong> ({fmt_delta('syndication_posts')}) &bull;
      Engagement Delta: <strong>{fmt_delta('syndication_engagement')}</strong>
    </div>
    <ul>
      {federation_html_items}
    </ul>

    <h2>🔁 Federation Deliverability &amp; Dead-Letter Queue</h2>
    <div class="grid">
      <div class="card">
        <div class="card-title">Pending Retries</div>
        <div class="card-val">{digest.get('dlq', {}).get('pending', 0)}</div>
      </div>
      <div class="card">
        <div class="card-title">Exhausted Failures</div>
        <div class="card-val">{digest.get('dlq', {}).get('exhausted', 0)}</div>
      </div>
      <div class="card">
        <div class="card-title">Successfully Replayed</div>
        <div class="card-val">{digest.get('dlq', {}).get('replayed', 0)}</div>
      </div>
    </div>

    <h2>🛡️ Federation Circuit Breaker Sentinel</h2>
    <ul>
      {cb_html_items}
    </ul>{pb_section_html}

    {heatmap_section_html}
    {recs_section_html}

    <footer>
      Autonomous Tactful Humor Operations Console &bull; Confidential Digest Report
    </footer>
  </div>
</body>
</html>"""
    return html
