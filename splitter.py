"""
Cross-Platform Content Splitting Module.

Handles automated chunking and thread segmentation for long-form text exceeding
platform character limits (Twitter/X: 280, Bluesky: 300, Mastodon: 500).
Preserves word boundaries and formats chunks with sequential indicators (e.g., "[1/3]").
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

PLATFORM_LIMITS = {
    "twitter": 280,
    "bluesky": 300,
    "mastodon": 500,
    "default": 280,
}


def split_text_into_chunks(text: str, max_chars: int = 280) -> List[str]:
    """
    Splits text into sequentially numbered chunks adhering to max_chars limit.
    If the text fits within max_chars, it is returned as a single item list without numbering.
    Otherwise, chunks are suffixed or prefixed with [i/N] indicators and split cleanly
    at word boundaries without splitting individual words unless a single word exceeds max_chars.
    """
    if not text:
        return []

    clean_text = text.strip()
    if len(clean_text) <= max_chars:
        return [clean_text]

    # Pre-calculate estimated number of parts. Indicator format: " [i/N]"
    # Typically 2-9 chunks. Start estimation with N=2.
    words = clean_text.split()
    estimated_n = max(2, (len(clean_text) // (max_chars - 10)) + 1)

    # Iterative refinement to ensure the indicator "[i/N]" does not push any chunk past max_chars
    for attempt_n in range(estimated_n, estimated_n + 10):
        chunks = []
        current_words = []
        current_len = 0
        part_idx = 1

        for word in words:
            indicator = f" [{part_idx}/{attempt_n}]"
            extra_len = len(word) + (1 if current_words else 0)
            if current_len + extra_len + len(indicator) <= max_chars:
                current_words.append(word)
                current_len += extra_len
            else:
                if not current_words:
                    # Single word exceeds capacity, hard split
                    hard_slice = word[:max_chars - len(indicator)]
                    current_words.append(hard_slice)
                    # Remaining part goes to next loop iteration
                    chunks.append(" ".join(current_words) + indicator)
                    part_idx += 1
                    current_words = [word[len(hard_slice):]]
                    current_len = len(current_words[0])
                else:
                    chunks.append(" ".join(current_words) + indicator)
                    part_idx += 1
                    current_words = [word]
                    current_len = len(word)

        if current_words:
            indicator = f" [{part_idx}/{attempt_n}]"
            chunks.append(" ".join(current_words) + indicator)

        if len(chunks) == attempt_n:
            return chunks
        elif len(chunks) < attempt_n:
            # Succeeded with fewer chunks than guessed; re-adjust and finalize
            final_n = len(chunks)
            final_chunks = []
            for i, ch in enumerate(chunks, 1):
                # Replace the old indicator with the accurate one
                base = ch.rsplit(" [", 1)[0]
                final_chunks.append(f"{base} [{i}/{final_n}]")
            return final_chunks

    # Fallback to last computed chunks
    return chunks


def split_for_platform(text: str, platform: str) -> List[str]:
    """
    Splits text according to the specific platform character limit.
    Supported platforms: 'twitter', 'bluesky', 'mastodon'.
    """
    limit = PLATFORM_LIMITS.get(platform.lower().strip(), PLATFORM_LIMITS["default"])
    return split_text_into_chunks(text, max_chars=limit)
