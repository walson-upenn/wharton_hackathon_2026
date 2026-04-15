"""
gap_score_components.py

Builds toward a per-property "gap" score that identifies which amenities
lack sufficient review coverage and are important enough to warrant
generating follow-up questions for new reviewers.

Four components feed into the final gap score:

    1. tag_amenity_mentioned   — is the amenity mentioned in this review? (1/0)
    2. score_amenity_sentiment — sentiment toward each mentioned amenity [-1.0, 1.0]
    3. score_amenity_detail    — how much concrete detail per mentioned amenity [0, 4]
    4. rank_amenity_importance — how important is each amenity for this property [0.0, 1.0]

Gap score intuition (to be defined):
    High gap = amenity is important to the property + poorly covered in reviews
    Low gap  = amenity is unimportant, or already well-covered with detail
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                                    # amenity_prompts (same dir)
sys.path.insert(0, os.path.join(_HERE, "../preprocessing"))  # review_amenity_tagger, amenity_normalizer

from openai import OpenAI
from review_amenity_tagger import load_csv, get_property_amenities, tag_review
from amenity_normalizer import normalize_amenities
from amenity_prompts import (
    prompt_tag_mentioned,
    prompt_score_sentiment,
    prompt_score_detail,
    prompt_rank_importance,
)

BASE      = os.path.dirname(os.path.abspath(__file__))
DESC_PATH = os.path.join(BASE, "../sources/Description_PROC.csv")
REV_PATH  = os.path.join(BASE, "../sources/Reviews_PROC.csv")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_amenities(
    property_id: str,
    desc_rows: list[dict],
    use_taxonomy: bool = True,
) -> list[str]:
    """Return the normalized (or raw) amenity list for a property."""
    raw = get_property_amenities(property_id, desc_rows)
    return normalize_amenities(raw) if use_taxonomy else raw


def _build_property_description(property_id: str, desc_rows: list[dict]) -> str:
    """
    Build a concise property context string from structured fields in desc_rows.
    Passed to prompt_rank_importance so the model can weight amenities by
    property identity (resort vs. business hotel, etc.).
    """
    row = next((r for r in desc_rows if r["eg_property_id"] == property_id), {})
    parts = []

    prop_type   = (row.get("property_type") or "").strip()
    star_rating = (row.get("star_rating") or "").strip()
    city        = (row.get("city") or "").strip()
    country     = (row.get("country") or "").strip()
    description = (row.get("property_description") or "").strip()

    if prop_type:
        parts.append(f"Property type: {prop_type}")
    if star_rating:
        parts.append(f"Star rating: {star_rating}")
    if city or country:
        parts.append(f"Location: {', '.join(filter(None, [city, country]))}")

    if description:
        parts.append(f"\n{description}")

    return "\n".join(parts)


# ── 1. Mention tagging ────────────────────────────────────────────────────────

def tag_amenity_mentioned(
    property_id: str,
    review_text: str,
    desc_rows: list[dict],
    client: OpenAI,
    use_taxonomy: bool = True,
) -> dict[str, int]:
    """
    Returns {amenity: 1 or 0} for every amenity listed at the property.

    1 = review mentions or clearly references the amenity (semantic matching
        applies — "jacuzzi" counts for "hot tub").
    0 = not mentioned.
    """
    amenities = _resolve_amenities(property_id, desc_rows, use_taxonomy)
    if not amenities:
        return {}
    return prompt_tag_mentioned(review_text, amenities, client)


# ── 2. Sentiment scoring ──────────────────────────────────────────────────────

def score_amenity_sentiment(
    property_id: str,
    review_text: str,
    desc_rows: list[dict],
    client: OpenAI,
    use_taxonomy: bool = True,
) -> dict[str, float]:
    """
    Returns {amenity: sentiment} for amenities mentioned in the review.
    Score is in [-1.0, 1.0]:
        -1.0 = strongly negative
        -0.5 = mildly negative
         0.0 = neutral / mixed
        +0.5 = mildly positive
        +1.0 = strongly positive

    Amenities not mentioned are omitted from the output.
    """
    amenities = _resolve_amenities(property_id, desc_rows, use_taxonomy)
    if not amenities:
        return {}
    return prompt_score_sentiment(review_text, amenities, client)


# ── 3. Detail scoring ─────────────────────────────────────────────────────────

def score_amenity_detail(
    property_id: str,
    review_text: str,
    desc_rows: list[dict],
    client: OpenAI,
    use_taxonomy: bool = True,
) -> dict[str, int]:
    """
    Returns {amenity: detail_score} for amenities mentioned in the review.
    Score is the sum of four binary criteria in [0, 4]:
        0  not mentioned
        1  vague mention only ("the pool was nice")
        2  at least one specific, verifiable attribute stated
        3  multiple distinct attributes or a clear reason given
        4  rich detail — comparisons, quantities, time/context clues

    Amenities scoring 0 (not mentioned) are omitted from the output.
    """
    amenities = _resolve_amenities(property_id, desc_rows, use_taxonomy)
    if not amenities:
        return {}
    all_scores = prompt_score_detail(review_text, amenities, client)
    return {a: s for a, s in all_scores.items() if s > 0}


# ── 4. Amenity importance ranking ─────────────────────────────────────────────

def rank_amenity_importance(
    property_id: str,
    desc_rows: list[dict],
    client: OpenAI,
    use_taxonomy: bool = True,
) -> dict[str, float]:
    """
    Returns {amenity: importance_score} in [0.0, 1.0] for every amenity
    at the property (pruned list via amenity_taxonomy.json).

    Combines two signals:
      A. General heuristics — wifi, breakfast, parking rank universally high;
         niche conveniences rank low
      B. Property-specific importance — inferred from the property description,
         type, and star rating (resort → pool critical; business hotel →
         business services outweigh outdoor activities)

    Tier → score:
        critical  → 1.0
        important → 0.67
        moderate  → 0.33
        minor     → 0.0
    """
    amenities = _resolve_amenities(property_id, desc_rows, use_taxonomy)
    if not amenities:
        return {}
    description = _build_property_description(property_id, desc_rows)
    return prompt_rank_importance(amenities, description, client)


# ── Main (smoke test) ─────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY environment variable.")

    client    = OpenAI(api_key=api_key)
    desc_rows = load_csv(DESC_PATH)
    rev_rows  = load_csv(REV_PATH)

    # Pick the first review with text for a quick smoke test
    sample = next(r for r in rev_rows if (r.get("review_text") or "").strip())
    pid    = sample["eg_property_id"]
    text   = sample["review_text"].strip()
    desc   = next((d for d in desc_rows if d["eg_property_id"] == pid), {})
    city   = desc.get("city", pid[:8])

    print(f"Property : {city} ({pid})")
    print(f"Review   : {text[:120]}...\n")

    print("── 1. tag_amenity_mentioned ──")
    tags = tag_amenity_mentioned(pid, text, desc_rows, client)
    mentioned = [a for a, v in tags.items() if v == 1]
    print(f"  {len(mentioned)}/{len(tags)} amenities mentioned")
    for a in mentioned[:5]:
        print(f"  [1] {a}")

    print("\n── 2. score_amenity_sentiment ──")
    sentiments = score_amenity_sentiment(pid, text, desc_rows, client)
    for a, s in sorted(sentiments.items(), key=lambda x: -x[1]):
        bar = "+" if s > 0 else ("-" if s < 0 else " ")
        print(f"  {bar}{abs(s):.1f}  {a}")

    print("\n── 3. score_amenity_detail ──")
    details = score_amenity_detail(pid, text, desc_rows, client)
    for a, s in sorted(details.items(), key=lambda x: -x[1]):
        print(f"  [{s}/4]  {a}")

    print("\n── 4. rank_amenity_importance ──")
    importance = rank_amenity_importance(pid, desc_rows, client)
    for a, s in sorted(importance.items(), key=lambda x: -x[1])[:10]:
        tier = {1.0: "critical", 0.67: "important", 0.33: "moderate", 0.0: "minor"}[s]
        print(f"  {tier:<10} {a}")


if __name__ == "__main__":
    main()
