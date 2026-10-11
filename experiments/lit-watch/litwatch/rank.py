"""Transparent keyword ranker: topic weights x title/abstract hits + recency.

Scores are comparable only within one config version. Every scored item
records which topics fired, so a digest reader can see *why* something
ranked. Tiers: candidate (>= candidate_threshold), watch (>= watch_threshold),
else noise (kept in store, omitted from digest).
"""

from __future__ import annotations

import re
from datetime import date


def _hits(text: str, keywords: list[str]) -> list[str]:
    found = []
    low = f" {text.lower()} "
    for kw in keywords:
        k = kw.lower()
        # Single short tokens (F4, F5, DLOG) match whole-word only; phrases
        # match as substrings so hyphen/space variants still hit.
        if " " in k or len(k) > 4:
            if k in low:
                found.append(kw)
        elif re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", low):
            found.append(kw)
    return found


def score_item(item: dict, topics, title_mult: float,
               today: date | None = None) -> tuple[float, list[str]]:
    """Return (score, topic names that fired)."""
    today = today or date.today()
    title = item.get("title", "") or ""
    abstract = item.get("abstract", "") or ""
    cats = " ".join(item.get("categories", []) or [])
    score = 0.0
    fired: list[str] = []
    for topic in topics:
        th = _hits(title, topic.keywords)
        ah = _hits(abstract + " " + cats, topic.keywords)
        if th or ah:
            fired.append(topic.name)
            score += topic.weight * (title_mult * len(th) + len(ah))
    if score > 0:
        pub = item.get("published") or item.get("updated")
        try:
            age = (today - date.fromisoformat(pub)).days if pub else None
        except ValueError:
            age = None
        if age is None:
            score *= 0.8  # undated: keep, rank lower
        elif age <= 7:
            score *= 1.25
        elif age <= 30:
            score *= 1.0
        else:
            score *= 0.6
    return round(score, 2), fired


def tier_of(score: float, candidate_threshold: float, watch_threshold: float) -> str:
    if score >= candidate_threshold:
        return "candidate"
    if score >= watch_threshold:
        return "watch"
    return "noise"


def rank_items(items: list[dict], config) -> list[tuple[dict, float, str, list[str]]]:
    scored = []
    for it in items:
        score, topics = score_item(it, config.topics, config.title_mult)
        scored.append((it, score,
                       tier_of(score, config.candidate_threshold, config.watch_threshold),
                       topics))
    scored.sort(key=lambda r: (-r[1], r[0].get("published") or ""))
    return scored
