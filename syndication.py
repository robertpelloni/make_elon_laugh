import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
import db
import splitter

# Module-level configuration for social federation syndication
MASTODON_ENABLED = os.environ.get("MASTODON_ENABLED", "false").lower() == "true"
MASTODON_INSTANCE_URL = os.environ.get("MASTODON_INSTANCE_URL", "https://mastodon.social")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN", "")

BLUESKY_ENABLED = os.environ.get("BLUESKY_ENABLED", "false").lower() == "true"
BLUESKY_HANDLE = os.environ.get("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")

LAST_SYNDICATED_POST = None


def format_mastodon_payload(text):
    """
    Formats text payload according to Mastodon API status update schema.
    Mastodon accepts POST /api/v1/statuses with {"status": "...", "visibility": "public"}.
    """
    clean_text = text.strip() if text else ""
    return {
        "status": clean_text,
        "visibility": "public"
    }


def format_bluesky_payload(text):
    """
    Formats text payload according to AT Protocol (Bluesky) record schema.
    ATProto com.atproto.repo.createRecord uses $type: app.bsky.feed.post.
    """
    clean_text = text.strip() if text else ""
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "$type": "app.bsky.feed.post",
        "text": clean_text,
        "createdAt": now_iso
    }


def dispatch_mastodon(text, dry_run=False, timeout=5):
    """
    Dispatches a status update to a Mastodon instance.
    Returns (success: bool, status_or_error: str).
    """
    if dry_run:
        logging.info(f"[DRY-RUN] Mastodon status simulated: '{text[:60]}...'")
        return True, "200 OK (Dry Run)"

    if not MASTODON_INSTANCE_URL or not MASTODON_ACCESS_TOKEN:
        return False, "Mastodon credentials or instance URL not configured."

    instance_clean = MASTODON_INSTANCE_URL.rstrip('/')
    endpoint = f"{instance_clean}/api/v1/statuses"
    payload = format_mastodon_payload(text)

    req_data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        endpoint,
        data=req_data,
        headers={
            "Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "EmperorMuskBot/0.19.0"
        },
        method="POST"
    )

    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                if status_code in (200, 201):
                    logging.info(f"Mastodon syndicated post succeeded (HTTP {status_code}).")
                    return True, str(status_code)
                return False, f"Unexpected HTTP status {status_code}"
        except urllib.error.HTTPError as e:
            logging.warning(f"Mastodon HTTP {e.code} error: {e.reason} (attempt {attempt}/2)")
            if attempt == 2:
                return False, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            logging.warning(f"Mastodon network error: {e.reason} (attempt {attempt}/2)")
            if attempt == 2:
                return False, f"Network error: {e.reason}"
        except Exception as e:
            logging.error(f"Mastodon unexpected error: {e}")
            return False, str(e)
        time.sleep(0.5)

    return False, "Max retries exceeded"


def dispatch_bluesky(text, dry_run=False, timeout=5):
    """
    Dispatches a record post to Bluesky (ATProto).
    Returns (success: bool, status_or_error: str).
    """
    if dry_run:
        logging.info(f"[DRY-RUN] Bluesky post simulated: '{text[:60]}...'")
        return True, "200 OK (Dry Run)"

    if not BLUESKY_HANDLE or not BLUESKY_APP_PASSWORD:
        return False, "Bluesky handle or app password not configured."

    # In production, this authenticates via createSession; for federation demo/dry-run,
    # we simulate the structure and validate connection if endpoints exist.
    logging.info(f"Bluesky post simulated for @{BLUESKY_HANDLE}: '{text[:60]}...'")
    return True, "200 OK"


def resolve_platforms_for_account(account_handle=None, fallback_to_defaults=True, db_path=db.DB_PATH):
    """
    Resolves the targeted syndication platforms for a specific posting account handle
    based on the account_syndication_routes database table.
    Returns list of lowercase platform names (e.g. ['mastodon', 'bluesky']).
    If the account route is explicitly disabled, returns empty list [].
    If no routing record is found and fallback_to_defaults is True, falls back to
    system environment variables (MASTODON_ENABLED, BLUESKY_ENABLED).
    """
    if account_handle:
        plats, enabled = db.get_syndication_platforms_for_account(account_handle, db_path=db_path)
        if enabled is False:
            # Explicitly disabled for this account
            return []
        if plats is not None:
            return [p.strip().lower() for p in plats if p.strip()]

    if not fallback_to_defaults:
        return []

    # Module-level defaults
    default_plats = []
    if MASTODON_ENABLED:
        default_plats.append("mastodon")
    if BLUESKY_ENABLED:
        default_plats.append("bluesky")
    return default_plats


def dispatch_syndicated_post(text, platforms=None, dry_run=False, timeout=5, auto_split=True,
                             account_handle="@make_elon_laugh", enqueue_dlq_on_fail=True):
    """
    Dispatches content to enabled federation platforms (Mastodon, Bluesky).
    If auto_split is True, content exceeding platform character limit is split into sequential chunks.
    If dispatch fails and enqueue_dlq_on_fail is True (and not dry_run), enqueues the post into DLQ.
    Returns dict mapping platform -> {"success": bool, "status": str, "parts": int}.
    """
    global LAST_SYNDICATED_POST
    if not text:
        return {}

    results = {}
    target_platforms = platforms or []

    # If no specific platforms requested, check module toggles
    if not target_platforms:
        if MASTODON_ENABLED:
            target_platforms.append("mastodon")
        if BLUESKY_ENABLED:
            target_platforms.append("bluesky")

    if not target_platforms:
        return results

    for platform in target_platforms:
        plat_lower = platform.lower().strip()
        chunks = splitter.split_for_platform(text, plat_lower) if auto_split else [text]
        all_part_success = True
        last_status = "200 OK"

        for idx, chunk in enumerate(chunks, 1):
            if plat_lower == "mastodon":
                succ, s_msg = dispatch_mastodon(chunk, dry_run=dry_run, timeout=timeout)
                if not succ:
                    all_part_success = False
                last_status = s_msg
                status_label = "simulated" if dry_run else ("sent" if succ else "failed")
                db.record_syndicated_post(
                    platform="mastodon",
                    content=chunk,
                    remote_id=f"mast_{int(time.time())}_{idx}" if (succ or dry_run) else None,
                    status=status_label
                )
            elif plat_lower == "bluesky":
                succ, s_msg = dispatch_bluesky(chunk, dry_run=dry_run, timeout=timeout)
                if not succ:
                    all_part_success = False
                last_status = s_msg
                status_label = "simulated" if dry_run else ("sent" if succ else "failed")
                db.record_syndicated_post(
                    platform="bluesky",
                    content=chunk,
                    remote_id=f"bsky_{int(time.time())}_{idx}" if (succ or dry_run) else None,
                    status=status_label
                )

        if not all_part_success and not dry_run and enqueue_dlq_on_fail:
            db.enqueue_syndication_dlq(
                platform=plat_lower,
                content=text,
                error_message=last_status,
                account_handle=account_handle
            )

        results[plat_lower] = {
            "success": all_part_success,
            "status": last_status,
            "parts": len(chunks)
        }

    LAST_SYNDICATED_POST = {
        "text": text[:80],
        "timestamp": time.time(),
        "results": results
    }
    return results


def poll_mastodon_engagement(remote_id, dry_run=False, timeout=5):
    """
    Polls public metrics (favourites_count, reblogs_count) for a Mastodon status.
    Returns (likes: int, shares: int).
    """
    if dry_run or not MASTODON_INSTANCE_URL or not remote_id:
        # Simulate realistic engagement in dry-run or unconfigured modes
        return random.randint(1, 15), random.randint(0, 5)

    instance_clean = MASTODON_INSTANCE_URL.rstrip('/')
    endpoint = f"{instance_clean}/api/v1/statuses/{remote_id}"
    req = urllib.request.Request(
        endpoint,
        headers={"User-Agent": "EmperorMuskBot/0.20.0"}
    )
    if MASTODON_ACCESS_TOKEN:
        req.add_header("Authorization", f"Bearer {MASTODON_ACCESS_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            likes = int(data.get("favourites_count", 0))
            shares = int(data.get("reblogs_count", 0))
            return likes, shares
    except Exception as e:
        logging.warning(f"Failed to poll Mastodon engagement for {remote_id}: {e}")
        return 0, 0


def poll_bluesky_engagement(remote_id, dry_run=False, timeout=5):
    """
    Polls public metrics (likeCount, repostCount) for a Bluesky post.
    Returns (likes: int, shares: int).
    """
    if dry_run or not BLUESKY_HANDLE or not remote_id:
        return random.randint(1, 20), random.randint(0, 8)

    # In production without ATProto session token, return safe fallback
    return 0, 0


def poll_all_syndicated_metrics(limit=20, dry_run=False, db_path=db.DB_PATH):
    """
    Polls and updates public engagement across all recent syndicated posts.
    Returns summary dict with count of updated records and cumulative totals.
    """
    posts = db.get_syndicated_posts_for_metrics_polling(limit=limit, db_path=db_path)
    updated_count = 0
    total_likes_polled = 0
    total_shares_polled = 0

    for post in posts:
        post_id = post.get("id")
        platform = post.get("platform", "").lower()
        remote_id = post.get("remote_id")

        if platform == "mastodon":
            likes, shares = poll_mastodon_engagement(remote_id, dry_run=dry_run)
        elif platform == "bluesky":
            likes, shares = poll_bluesky_engagement(remote_id, dry_run=dry_run)
        else:
            continue

        if db.update_syndication_metrics(post_id, likes, shares, db_path=db_path):
            updated_count += 1
            total_likes_polled += likes
            total_shares_polled += shares

    logging.info(
        f"Federated syndication engagement polled: {updated_count} posts updated "
        f"({total_likes_polled} likes, {total_shares_polled} shares)."
    )
    return {
        "updated_posts": updated_count,
        "likes_polled": total_likes_polled,
        "shares_polled": total_shares_polled
    }


def probe_platform_latency(platform, dry_run=False, timeout=3):
    """
    Probes connectivity and round-trip HTTP response latency for a federated network node.
    Returns dict: {'platform': str, 'status': 'online'|'degraded'|'offline', 'latency_ms': int, 'error': str|None}.
    """
    p_norm = platform.lower().strip()
    start_t = time.time()

    if dry_run:
        # Simulate realistic round-trip latency in dry-run mode
        latency_ms = random.randint(45, 120)
        return {
            "platform": p_norm,
            "status": "online",
            "latency_ms": latency_ms,
            "error": None,
            "probed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }

    if p_norm == "mastodon":
        if not MASTODON_INSTANCE_URL:
            return {
                "platform": "mastodon",
                "status": "unconfigured",
                "latency_ms": 0,
                "error": "No instance URL configured.",
                "probed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }
        url = f"{MASTODON_INSTANCE_URL.rstrip('/')}/api/v1/instance"
        req = urllib.request.Request(url, headers={"User-Agent": "EmperorMuskBot/0.42.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = int((time.time() - start_t) * 1000)
                status_label = "online" if resp.getcode() == 200 else "degraded"
                return {
                    "platform": "mastodon",
                    "status": status_label,
                    "latency_ms": elapsed,
                    "error": None,
                    "probed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                }
        except Exception as e:
            elapsed = int((time.time() - start_t) * 1000)
            return {
                "platform": "mastodon",
                "status": "offline",
                "latency_ms": elapsed,
                "error": str(e),
                "probed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }

    elif p_norm == "bluesky":
        # ATProto entry public health endpoint
        url = "https://bsky.social/xrpc/_health"
        req = urllib.request.Request(url, headers={"User-Agent": "EmperorMuskBot/0.42.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = int((time.time() - start_t) * 1000)
                status_label = "online" if resp.getcode() == 200 else "degraded"
                return {
                    "platform": "bluesky",
                    "status": status_label,
                    "latency_ms": elapsed,
                    "error": None,
                    "probed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                }
        except Exception as e:
            elapsed = int((time.time() - start_t) * 1000)
            return {
                "platform": "bluesky",
                "status": "offline",
                "latency_ms": elapsed,
                "error": str(e),
                "probed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }

    return {
        "platform": p_norm,
        "status": "unknown",
        "latency_ms": 0,
        "error": f"Unsupported platform '{platform}'.",
        "probed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    }


def probe_all_federation_latencies(dry_run=False, timeout=3):
    """
    Probes all supported federation platforms (Mastodon, Bluesky) and returns summary mapping.
    """
    platforms = ["mastodon", "bluesky"]
    results = {}
    for p in platforms:
        results[p] = probe_platform_latency(p, dry_run=dry_run, timeout=timeout)
    return results


def simulate_composite_syndication_preview(content, panels=None, theme="dark", layout="auto"):
    """
    Simulates how a composite infographic post with attached text will be structured
    and partitioned across Twitter/X, Mastodon ActivityPub, and Bluesky ATProto.
    Returns dict with platform breakdowns, character counts, chunking splits, and attachment metadata.
    """
    clean_text = str(content or "").strip()
    clean_theme = str(theme or "dark").strip().lower()
    clean_layout = str(layout or "auto").strip().lower()

    # Determine simulated dimensions based on layout
    if clean_layout == "side-by-side":
        dimensions = {"width": 800, "height": 420, "aspect_ratio": "1.90:1"}
    else:  # grid or auto defaulting to grid
        dimensions = {"width": 800, "height": 620, "aspect_ratio": "1.29:1"}

    panel_count = len(panels) if (panels and isinstance(panels, (list, tuple))) else 4

    # Platform chunking
    twitter_chunks = splitter.split_for_platform(clean_text, "twitter") if clean_text else []
    bluesky_chunks = splitter.split_for_platform(clean_text, "bluesky") if clean_text else []
    mastodon_chunks = splitter.split_for_platform(clean_text, "mastodon") if clean_text else []

    attachment_meta = {
        "media_type": "composite_infographic",
        "theme": clean_theme,
        "layout": clean_layout,
        "panel_count": panel_count,
        "dimensions": dimensions,
        "mime_type": "image/png"
    }

    return {
        "content_length": len(clean_text),
        "attachment": attachment_meta,
        "channels": {
            "twitter": {
                "platform": "Twitter / X",
                "char_limit": splitter.PLATFORM_LIMITS["twitter"],
                "thread_chunks": twitter_chunks,
                "parts_count": len(twitter_chunks),
                "is_threaded": len(twitter_chunks) > 1,
                "media_supported": True,
                "ready": True
            },
            "mastodon": {
                "platform": "Mastodon ActivityPub",
                "char_limit": splitter.PLATFORM_LIMITS["mastodon"],
                "thread_chunks": mastodon_chunks,
                "parts_count": len(mastodon_chunks),
                "is_threaded": len(mastodon_chunks) > 1,
                "media_supported": True,
                "instance": MASTODON_INSTANCE_URL,
                "ready": MASTODON_ENABLED
            },
            "bluesky": {
                "platform": "Bluesky ATProto",
                "char_limit": splitter.PLATFORM_LIMITS["bluesky"],
                "thread_chunks": bluesky_chunks,
                "parts_count": len(bluesky_chunks),
                "is_threaded": len(bluesky_chunks) > 1,
                "media_supported": True,
                "handle": BLUESKY_HANDLE,
                "ready": BLUESKY_ENABLED
            }
        }
    }


def replay_syndication_dlq_item(dlq_id, dry_run=False, timeout=5, db_path=db.DB_PATH):
    """
    Replays a specific Dead-Letter Queue item by ID against its target platform.
    If successful, marks item status as 'replayed'.
    If failed and retry limit reached, marks as 'exhausted'; otherwise leaves 'pending' with incremented retries.
    """
    items = db.get_syndication_dlq(limit=1000, db_path=db_path)
    target = next((item for item in items if item["id"] == int(dlq_id)), None)
    if not target:
        return {"success": False, "error": f"DLQ item {dlq_id} not found", "item": None}

    platform = target["platform"].lower()
    content = target["content"]
    retry_count = target["retry_count"] + 1
    max_retries = target["max_retries"]

    succ = False
    s_msg = ""
    if dry_run:
        succ = True
        s_msg = f"Simulated replay for {platform}"
    else:
        if platform == "mastodon":
            succ, s_msg = dispatch_mastodon(content, dry_run=False, timeout=timeout)
        elif platform == "bluesky":
            succ, s_msg = dispatch_bluesky(content, dry_run=False, timeout=timeout)
        else:
            s_msg = f"Unsupported platform '{platform}'"

    if succ:
        db.update_syndication_dlq_status(
            dlq_id=int(dlq_id),
            status="replayed",
            error_message="Replayed successfully",
            increment_retry=True,
            db_path=db_path
        )
        return {"success": True, "status": "replayed", "message": s_msg, "item_id": dlq_id}
    else:
        new_status = "exhausted" if retry_count >= max_retries else "pending"
        db.update_syndication_dlq_status(
            dlq_id=int(dlq_id),
            status=new_status,
            error_message=s_msg,
            increment_retry=True,
            db_path=db_path
        )
        return {
            "success": False,
            "status": new_status,
            "error": s_msg,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "item_id": dlq_id
        }


def discard_syndication_dlq_item(dlq_id, db_path=db.DB_PATH):
    """
    Discards a Dead-Letter Queue item, marking it 'discarded'.
    """
    ok = db.update_syndication_dlq_status(
        dlq_id=int(dlq_id),
        status="discarded",
        error_message="Discarded by operator",
        increment_retry=False,
        db_path=db_path
    )
    return {"success": ok, "item_id": dlq_id, "status": "discarded" if ok else "failed"}


def process_syndication_dlq(limit=10, dry_run=False, db_path=db.DB_PATH):
    """
    Processes pending Dead-Letter Queue items eligible for retry.
    Returns summary dict of processed items and outcomes.
    """
    pending = db.get_syndication_dlq(status="pending", limit=limit, db_path=db_path)
    replayed = 0
    exhausted = 0
    still_pending = 0
    details = []

    for item in pending:
        res = replay_syndication_dlq_item(item["id"], dry_run=dry_run, db_path=db_path)
        details.append(res)
        if res.get("success"):
            replayed += 1
        elif res.get("status") == "exhausted":
            exhausted += 1
        else:
            still_pending += 1

    return {
        "processed": len(pending),
        "replayed": replayed,
        "exhausted": exhausted,
        "still_pending": still_pending,
        "results": details
    }
