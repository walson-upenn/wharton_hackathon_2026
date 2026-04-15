"""
AskScore: determines which amenities to ask the next reviewer about,
prioritizing questions that most improve understanding of the hotel.

Inputs:
  - final-preprocessing/review_profiles.json   (per-review amenity mentions)
  - final-preprocessing/amenity_profiles.json   (per-hotel amenity criticality)
  - final-preprocessing/aggregated_reasons.json (representative reason snippets)

Output: per-hotel ranked list of amenities with scores, components, and context.
"""

from __future__ import annotations
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ── Parameters ──────────────────────────────────────────────────────────────

ALPHA = 1.0                             # criticality exponent

# Coverage saturation thresholds
COVERAGE_SAT = 10                       # num mentions to reach ~63% coverage
DEPTH_MAX = 4                           # max detail score per mention

# Disagreement: negative fraction = neg / (pos + neg)
MIN_MENTIONS_FOR_DISAGREEMENT = 3       # need at least this many
SENTIMENT_THRESHOLD = 0.25             # |s| > this to count as pos/neg

# Trend: two-window delta (old vs recent sentiment)
TREND_WINDOW_DAYS = 90                  # boundary between "recent" and "old"
MIN_TREND_MENTIONS = 2                  # need >= this many in EACH window

# Recency / staleness
TAU_R = 365                             # staleness saturation (days); ~1yr half-life

# Component weights
W_DETAIL = 0.40
W_DISAGREEMENT = 0.20
W_TREND = 0.20
W_RECENCY = 0.15


def parse_date(s: str) -> datetime:
    """Parse m/d/yy date strings."""
    return datetime.strptime(s, "%m/%d/%y")


def saturate(x: float, tau: float) -> float:
    """0-1 saturating curve: 0 at x=0, approaches 1 as x grows."""
    return 1 - math.exp(-x / tau)


def compute_scores(review_profiles: dict, amenity_profiles: dict,
                   aggregated_reasons: dict, reference_date: datetime | None = None):
    """
    Returns dict[hotel_id] -> list of {amenity, score, components, context}
    sorted descending by score.
    """
    if reference_date is None:
        # use the latest review date across all hotels as "today"
        all_dates = []
        for reviews in review_profiles.values():
            for r in reviews:
                try:
                    all_dates.append(parse_date(r["date"]))
                except ValueError:
                    pass
        reference_date = max(all_dates) if all_dates else datetime.now()

    results = {}

    for hotel_id, reviews in review_profiles.items():
        criticalities = amenity_profiles.get(hotel_id, {})
        hotel_reasons = aggregated_reasons.get(hotel_id, {})
        all_amenities = set(criticalities.keys())

        # ── Gather per-amenity mention data ────────────────────────────
        # Only track actual mentions (non-mentions affect coverage via
        # total_reviews denominator, not as explicit zero entries)
        amenity_mentions: dict[str, list[dict]] = defaultdict(list)
        total_reviews = 0

        for review in reviews:
            try:
                review_date = parse_date(review["date"])
            except ValueError:
                continue
            age = (reference_date - review_date).days
            total_reviews += 1

            for amenity, info in review["amenities"].items():
                all_amenities.add(amenity)
                amenity_mentions[amenity].append({
                    "age": age,
                    "detail": info["detail"],
                    "sentiment": info["sentiment"],
                })

        if total_reviews == 0:
            results[hotel_id] = []
            continue

        # ── Score each amenity ──────────────────────────────────────────
        scored = []
        for amenity in sorted(all_amenities):
            mentions = [m for m in amenity_mentions[amenity]
                        if m["sentiment"] is not None]
            C = criticalities.get(amenity, 0.0)
            n = len(mentions)

            # ── 1. Detail Gap = 1 - coverage * depth ───────────────────
            # coverage: what fraction of reviews mention this amenity (saturating)
            coverage = saturate(n, COVERAGE_SAT)  # 0→0, ~10→0.63, ~23→0.90
            # depth: average detail of mentions / max detail (0 if no mentions)
            if n > 0:
                avg_detail = sum(m["detail"] for m in mentions) / n
                depth = avg_detail / DEPTH_MAX    # 0-1
            else:
                depth = 0.0
            knowledge_gap_score = 1 - coverage * depth     # 0-1

            # ── 2. Disagreement = neg / (pos + neg) ────────────────────
            # Only counts as controversy_score when there's an actual minority of
            # negative opinions among opinionated reviews. Peaks at 0.5 (50/50).
            n_pos = sum(1 for m in mentions if m["sentiment"] > SENTIMENT_THRESHOLD)
            n_neg = sum(1 for m in mentions if m["sentiment"] < -SENTIMENT_THRESHOLD)
            n_neu = n - n_pos - n_neg
            if n >= MIN_MENTIONS_FOR_DISAGREEMENT and (n_pos + n_neg) > 0:
                # Controversy score: peaks at 1.0 when 50/50 split, 0 when all one side
                # p=0.0 (all pos) → 0, p=0.5 (split) → 1.0, p=1.0 (all neg) → 0
                p = n_neg / (n_pos + n_neg)
                controversy_score = 4 * p * (1 - p)
            else:
                controversy_score = 0.0                # not enough data to judge

            # ── 3. Decline Score = two-window delta (old → recent) ───
            # Only fires when sentiment is actually declining.
            recent_mentions = [m for m in mentions if m["age"] <= TREND_WINDOW_DAYS]
            old_mentions = [m for m in mentions if m["age"] > TREND_WINDOW_DAYS]

            if (len(recent_mentions) >= MIN_TREND_MENTIONS
                    and len(old_mentions) >= MIN_TREND_MENTIONS):
                s_recent = sum(m["sentiment"] for m in recent_mentions) / len(recent_mentions)
                s_old = sum(m["sentiment"] for m in old_mentions) / len(old_mentions)
                decline_score = max(0.0, min(1.0, s_old - s_recent))
            else:
                decline_score = 0.0
                s_recent = None

            # ── 4. Recency = exponential staleness ─────────────────────
            if n > 0:
                days_since = min(m["age"] for m in mentions)
                staleness_score = 1 - math.exp(-days_since / TAU_R)
            else:
                days_since = None
                staleness_score = 1.0                     # never mentioned → maximally stale

            # ── 5. Final AskScore ──────────────────────────────────────
            C_term = C ** ALPHA if C > 0 else 0.0
            base = (W_DETAIL * knowledge_gap_score
                    + W_DISAGREEMENT * controversy_score
                    + W_TREND * decline_score
                    + W_RECENCY * staleness_score)
            ask_score = C_term * base

            # ── Context for output ─────────────────────────────────────
            reasons = hotel_reasons.get(amenity, {})
            pos_reasons = reasons.get("positive", [])
            neg_reasons = reasons.get("negative", [])

            scored.append({
                "amenity": amenity,
                "score": round(ask_score, 4),
                "criticality": C,
                "components": {
                    "knowledge_gap_score": round(knowledge_gap_score, 4),
                    "controversy_score": round(controversy_score, 4),
                    "decline_score": round(decline_score, 4),
                    "staleness_score": round(staleness_score, 4),
                },
                "stats": {
                    "num_mentions": n,
                    "coverage": round(coverage, 3),
                    "avg_detail": round(avg_detail, 2) if n > 0 else None,
                    "mean_sentiment": round(sum(m["sentiment"] for m in mentions) / n, 3) if n > 0 else None,
                    "recent_mean_sentiment": round(s_recent, 3) if s_recent is not None else None,
                    "num_positive": n_pos,
                    "num_negative": n_neg,
                    "num_neutral": n_neu,
                    "days_since_last_mention": days_since,
                },
                "context": {
                    "positive_reasons": pos_reasons[:5],
                    "negative_reasons": neg_reasons[:5],
                },
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        results[hotel_id] = scored

    return results


def print_top_amenities(results: dict, top_n: int = 5):
    """Pretty-print top amenities per hotel."""
    for hotel_id, amenities in results.items():
        print(f"\n{'='*70}")
        print(f"Hotel: {hotel_id[:12]}...")
        print(f"{'='*70}")
        for i, item in enumerate(amenities[:top_n], 1):
            c = item["components"]
            s = item["stats"]
            print(f"\n  #{i} {item['amenity']}  (score={item['score']:.4f})")
            print(f"      criticality={item['criticality']:.2f}  "
                  f"mentions={s['num_mentions']}  "
                  f"coverage={s['coverage']:.2f}  "
                  f"avg_detail={s['avg_detail']}  "
                  f"mean_sent={s['mean_sentiment']}")
            print(f"      knowledge_gap_score={c['knowledge_gap_score']:.3f}  "
                  f"controversy_score={c['controversy_score']:.3f}  "
                  f"decline_score={c['decline_score']:.3f}  "
                  f"staleness_score={c['staleness_score']:.3f}")
            if item["context"]["negative_reasons"]:
                print(f"      neg: {item['context']['negative_reasons'][:3]}")
            if item["context"]["positive_reasons"]:
                print(f"      pos: {item['context']['positive_reasons'][:3]}")


def main():
    base = Path(__file__).resolve().parent.parent / "final-preprocessing"

    with open(base / "review_profiles.json") as f:
        review_profiles = json.load(f)
    with open(base / "amenity_profiles.json") as f:
        amenity_profiles = json.load(f)
    with open(base / "aggregated_reasons.json") as f:
        aggregated_reasons = json.load(f)

    results = compute_scores(
        review_profiles, amenity_profiles, aggregated_reasons)

    # Save full results
    out_path = Path(__file__).resolve().parent / "ask_scores.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved full results to {out_path}")

    # Print summary
    print_top_amenities(results)


if __name__ == "__main__":
    main()
