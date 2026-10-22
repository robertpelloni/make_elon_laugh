# make_elon_laugh

**This repository contains no code.** Its only file is the document that
used to be this README: a chat transcript that designs a joke X/Twitter
bot and drafts its script inline. Nothing was ever extracted into a `.py`
file, and there is no evidence in the repo that the bot was run.

## The concept (from the document)

A bot that replies to every post by Elon Musk (user ID 44196397) addressing
him as "Emperor Musk", recommending the 1992 Danish cult parody film
*Gayniggers from Outer Space*, and attaching a rotating psytrance track
about aliens/Mars (Astral Projection, Infected Mushroom, Pleiadians,
Hallucinogen, 1200 Micrograms, Shpongle) — an attempt to make him laugh
through sheer old-internet absurdity.

## What the document actually contains

1. A feasibility analysis: X API read access is pay-per-use (no viable free
   tier for tracking a timeline), and a fast-reply bot aimed at the
   platform's most-viewed account is a prime suspension target.
2. A moderation-risk analysis: the film's title contains a racial slur and
   would likely trip automated hate-speech/spam filters despite being a
   real historical film title; workarounds discussed include posting the
   title as an image ("Space Movie 1992" meme) instead of text.
3. A semi-manual alternative: notifications + a prepared copypasta file.
4. A complete draft script (Tweepy v4, API v2): poll Musk's tweets every
   60 s, keep a local replied-ID cache to avoid duplicate paid reads/replies,
   post a randomized reply; with implementation warnings (app needs
   Read+Write OAuth 1.0a permissions or replies 403).

## Status

Concept document, written in a single session on 2026-07-12 (two commits).
If anyone builds it: extract the script from the transcript in git history,
expect per-read/per-post API charges, and expect the account to be
suspended quickly — that outcome is the document's own prediction.
