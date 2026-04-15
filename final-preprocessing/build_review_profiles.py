"""
build_review_profiles.py

Builds a JSON file containing per-review amenity analysis for every property.

Pipeline per review:
    Stage 1 — tag_mentioned       : which amenities are referenced? (1/0)
    Stage 2 — sentiment + detail  : parallel, only on mentioned amenities
    Stage 3 — reasons             : only on non-neutral amenities

Reviews where no amenities are mentioned are omitted from the output entirely.

Output structure (review_profiles.json):
    {
        "<property_id>": [
            {
                "date":  "...",
                "title": "...",
                "text":  "...",
                "amenities": {
                    "<amenity>": {
                        "sentiment": float or null,
                        "detail":    int (0–4),
                        "reasons":   [str, ...]
                    },
                    ...
                }
            },
            ...
        ],
        ...
    }

Resumable: properties already fully written to the output file are skipped.
Checkpoints after each completed property.

Run:
    OPENAI_API_KEY=sk-... python build_review_profiles.py [--workers N] [--property <id>]

    --workers N       total concurrent reviews across all properties (default: 20)
    --property <id>   process a single property and print results (for testing)
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "../preprocessing"))

from openai import OpenAI
from review_amenity_tagger import load_csv, get_property_amenities
from amenity_normalizer import normalize_amenities
from amenity_prompts import (
    prompt_tag_mentioned,
    prompt_score_sentiment,
    prompt_score_detail,
    prompt_extract_reason,
)

BASE        = _HERE
DESC_PATH   = os.path.join(BASE, "../sources/Description_PROC.csv")
REV_PATH    = os.path.join(BASE, "../sources/Reviews_PROC.csv")
OUTPUT_PATH = os.path.join(BASE, "review_profiles.json")


# ── Per-review pipeline ───────────────────────────────────────────────────────

def process_review(review_text: str, amenities: list[str], client: OpenAI) -> dict:
    """
    Runs the full 3-stage pipeline for a single review.
    Returns {amenity: {sentiment, detail, reasons}} for mentioned amenities only.
    Returns an empty dict if nothing was mentioned.
    """
    # Stage 1 — tag
    tags      = prompt_tag_mentioned(review_text, amenities, client)
    mentioned = [a for a, v in tags.items() if v == 1]
    if not mentioned:
        return {}

    # Stage 2 — sentiment + detail in parallel
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_sent = ex.submit(prompt_score_sentiment, review_text, mentioned, client)
        f_det  = ex.submit(prompt_score_detail,    review_text, mentioned, client)
    sentiments = f_sent.result()
    details    = f_det.result()

    # Stage 3 — reasons for non-neutral amenities only
    non_neutral = {a: s for a, s in sentiments.items() if s != 0.0}
    reasons = prompt_extract_reason(review_text, non_neutral, client) if non_neutral else {}

    return {
        a: {
            "sentiment": sentiments.get(a),
            "detail":    details.get(a, 0),
            "reasons":   reasons.get(a, []),
        }
        for a in mentioned
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers",  type=int, default=20,   help="total concurrent reviews (default: 20)")
    parser.add_argument("--property", type=str, default=None, help="process a single property (for testing)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY environment variable.")

    client    = OpenAI(api_key=api_key)
    desc_rows = load_csv(DESC_PATH)
    rev_rows  = load_csv(REV_PATH)

    # Build lookups
    prop_lookup = {r["eg_property_id"]: r for r in desc_rows}
    reviews_by_property: dict[str, list[dict]] = {}
    for r in rev_rows:
        text = (r.get("review_text") or "").strip()
        if not text:
            continue
        pid = r["eg_property_id"]
        reviews_by_property.setdefault(pid, []).append({
            "date":  r.get("acquisition_date", ""),
            "title": (r.get("review_title") or "").strip(),
            "text":  text,
        })

    # Load existing output for resumption
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            output = json.load(f)
        print(f"Resuming — {len(output)} properties already done.")
    else:
        output = {}

    # Determine which properties to process
    if args.property:
        targets = [args.property]
    else:
        targets = [pid for pid in reviews_by_property if pid not in output]

    # Resolve amenities for each target property
    amenities_by_property = {}
    for pid in targets:
        raw = get_property_amenities(pid, desc_rows)
        amenities_by_property[pid] = normalize_amenities(raw)

    targets = [pid for pid in targets if amenities_by_property.get(pid)]

    # Flatten all (property_id, review_index, review) into one work list
    all_work = []
    review_counts = {}
    for pid in targets:
        reviews = reviews_by_property.get(pid, [])
        review_counts[pid] = len(reviews)
        for i, r in enumerate(reviews):
            all_work.append((pid, i, r))

    total_reviews = len(all_work)
    print(f"Properties to process : {len(targets)}")
    print(f"Total reviews         : {total_reviews}")
    print(f"Concurrent workers    : {args.workers}\n")

    # Buffers for assembling results per property
    results_buffer  = defaultdict(dict)   # pid -> {idx: record}
    completed_count = defaultdict(int)    # pid -> number of reviews finished

    def _run(pid, idx, review):
        amenities    = amenities_by_property[pid]
        amenity_data = process_review(review["text"], amenities, client)
        return pid, idx, review, amenity_data

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_run, pid, idx, r): (pid, idx) for pid, idx, r in all_work}

        for future in as_completed(futures):
            pid, idx, review, amenity_data = future.result()
            done += 1

            # Only store reviews where at least one amenity was mentioned
            if amenity_data:
                results_buffer[pid][idx] = {
                    "date":      review["date"],
                    "title":     review["title"],
                    "text":      review["text"],
                    "amenities": amenity_data,
                }

            completed_count[pid] += 1
            print(f"  [{done}/{total_reviews}] {pid[:8]}… review {idx} done", flush=True)

            # When all reviews for a property are done, checkpoint
            if completed_count[pid] == review_counts[pid]:
                records = [
                    results_buffer[pid][i]
                    for i in sorted(results_buffer[pid])
                ]
                city = prop_lookup.get(pid, {}).get("city", pid[:8])

                if args.property:
                    print(json.dumps({pid: records}, indent=2))
                else:
                    output[pid] = records
                    with open(OUTPUT_PATH, "w") as f:
                        json.dump(output, f, indent=2)
                    print(f"  ✓ {city} ({pid[:8]}…) — {len(records)} reviews saved "
                          f"({len(output)} properties total)\n")

    if not args.property:
        print(f"\nDone. Output written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
