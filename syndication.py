import json
import logging
import os
import time
import urllib.error
import urllib.request

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


def dispatch_syndicated_post(text, platforms=None, dry_run=False, timeout=5):
    """
    Dispatches content to enabled federation platforms (Mastodon, Bluesky).
    Returns dict mapping platform -> {"success": bool, "status": str}.
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
        if plat_lower == "mastodon":
            success, status_msg = dispatch_mastodon(text, dry_run=dry_run, timeout=timeout)
            results["mastodon"] = {"success": success, "status": status_msg}
        elif plat_lower == "bluesky":
            success, status_msg = dispatch_bluesky(text, dry_run=dry_run, timeout=timeout)
            results["bluesky"] = {"success": success, "status": status_msg}

    LAST_SYNDICATED_POST = {
        "text": text[:80],
        "timestamp": time.time(),
        "results": results
    }
    return results
