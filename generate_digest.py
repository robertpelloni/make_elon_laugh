#!/usr/bin/env python3
"""
Automated Weekly Performance Digest CLI Generator.

This utility compiles rolling performance metrics from the local SQLite database
(including tweet replies, likes/retweets engagement, scheduled tweet statuses,
and community humor feedback) and exports structured Markdown and JSON reports
to a designated reports directory or stdout.
"""

import argparse
import datetime
import json
import logging
import os
import sys

from digest import export_digest_html, export_digest_markdown, generate_performance_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("digest_generator")


def save_digest_files(
    digest_data: dict,
    out_dir: str,
    export_format: str = "all",
    prefix: str = "digest",
    json_indent: int = 2
) -> dict:
    """
    Saves digest data to disk in markdown, html, and/or JSON formats.

    Returns a dictionary mapping format names to their saved file paths.
    """
    os.makedirs(out_dir, exist_ok=True)
    clean_prefix = "".join(c for c in prefix if c.isalnum() or c in ("-", "_")).strip() or "digest"
    timestamp_slug = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    saved_paths = {}

    if export_format in ("markdown", "both", "all"):
        md_content = export_digest_markdown(digest_data)
        md_filename = f"{clean_prefix}_{timestamp_slug}.md"
        md_path = os.path.join(out_dir, md_filename)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        saved_paths["markdown"] = md_path
        logger.info(f"Exported Markdown digest: {md_path}")

    if export_format in ("html", "all"):
        html_content = export_digest_html(digest_data)
        html_filename = f"{clean_prefix}_{timestamp_slug}.html"
        html_path = os.path.join(out_dir, html_filename)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        saved_paths["html"] = html_path
        logger.info(f"Exported HTML digest: {html_path}")

    if export_format in ("json", "both", "all"):
        json_filename = f"{clean_prefix}_{timestamp_slug}.json"
        json_path = os.path.join(out_dir, json_filename)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(digest_data, f, indent=json_indent)
        saved_paths["json"] = json_path
        logger.info(f"Exported JSON digest: {json_path}")

    return saved_paths


def main(cli_args=None):
    parser = argparse.ArgumentParser(
        description="Generate and export automated weekly performance digests for Emperor Musk Bot."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Rolling aggregation window in days (default: 7)"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="bot_data.db",
        help="Path to SQLite database file (default: bot_data.db)"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="reports",
        help="Directory to save exported digest reports (default: reports)"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="digest",
        help="Filename prefix for generated reports (default: digest)"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "html", "json", "both", "all", "stdout"],
        default="all",
        help="Export format (default: all)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational console output"
    )
    parser.add_argument(
        "--json-indent",
        type=int,
        default=2,
        help="Number of spaces for JSON output indentation (default: 2)"
    )
    parser.add_argument(
        "--account",
        type=str,
        default=None,
        help="Optional target account handle to filter scheduled queue reports (e.g. @make_elon_laugh)"
    )

    args = parser.parse_args(cli_args)

    if args.quiet:
        logger.setLevel(logging.WARNING)

    try:
        logger.info(f"Generating performance digest (window: {args.days} days, db: {args.db_path})...")
        digest_data = generate_performance_digest(db_path=args.db_path, days=args.days)

        if args.format == "stdout":
            print(export_digest_markdown(digest_data))
            return 0

        saved = save_digest_files(
            digest_data,
            out_dir=args.out_dir,
            export_format=args.format,
            prefix=args.prefix,
            json_indent=args.json_indent
        )
        if not args.quiet:
            for fmt, path in saved.items():
                print(f"[{fmt.upper()}] {path}")
        return 0
    except Exception as e:
        logger.error(f"Failed to generate performance digest: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
