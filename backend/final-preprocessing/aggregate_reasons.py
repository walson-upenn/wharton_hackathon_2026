"""
aggregate_reasons.py

Reads review_profiles.json and, for each property and each amenity,
aggregates reasons from positive and negative sentiment reviews across
all reviews, then consolidates them into at most 3 clean, specific,
representative reasons per sentiment direction.

Output structure (aggregated_reasons.json):
    {
        "<property_id>": {
            "<amenity>": {
                "positive": ["reason1", "reason2"],   (at most 3)
                "negative": ["reason1"]               (at most 3)
            },
            ...
        },
        ...
    }

Amenities with no extractable reasons after consolidation are omitted.
Properties with no amenity reasons at all are omitted.

Run:
    OPENAI_API_KEY=sk-... python aggregate_reasons.py [--workers N] [--property <id>]

    --workers N       concurrent properties (default: 20)
    --property <id>   process a single property and print result (for testing)
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
from amenity_prompts import prompt_consolidate_reasons

BASE            = _HERE
PROFILES_PATH   = os.path.join(BASE, "review_profiles.json")
OUTPUT_PATH     = os.path.join(BASE, "aggregated_reasons.json")


def collect_reasons(property_reviews: list[dict]) -> dict[str, dict[str, list[str]]]:
    """
    Aggregates raw reasons from all reviews for a property into:
        {amenity: {"positive": [...], "negative": [...]}}

    A reason is bucketed as positive if the review's sentiment > 0,
    negative if sentiment < 0. Neutral/null sentiment reviews are skipped.
    """
    buckets: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for review in property_reviews:
        for amenity, data in review.get("amenities", {}).items():
            sentiment = data.get("sentiment")
            reasons   = data.get("reasons", [])

            if not reasons or sentiment is None or sentiment == 0.0:
                continue

            direction = "positive" if sentiment > 0 else "negative"
            buckets[amenity][direction].extend(reasons)

    # Convert defaultdicts to plain dicts; drop amenities with no reasons
    return {
        amenity: dict(directions)
        for amenity, directions in buckets.items()
        if any(directions.values())
    }


def process_property(
    pid: str,
    property_reviews: list[dict],
    client: OpenAI,
) -> dict[str, dict[str, list[str]]]:
    """
    Collects and consolidates reasons for a single property.
    Returns the consolidated {amenity: {positive, negative}} dict.
    """
    raw_reasons = collect_reasons(property_reviews)
    if not raw_reasons:
        return {}
    return prompt_consolidate_reasons(raw_reasons, client)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers",  type=int, default=20,   help="concurrent properties (default: 20)")
    parser.add_argument("--property", type=str, default=None, help="process a single property (for testing)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY environment variable.")

    if not os.path.exists(PROFILES_PATH):
        sys.exit(f"review_profiles.json not found at {PROFILES_PATH} — run build_review_profiles.py first.")

    with open(PROFILES_PATH) as f:
        profiles = json.load(f)

    # Load existing output for resumption
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            output = json.load(f)
        print(f"Resuming — {len(output)} properties already done.")
    else:
        output = {}

    client = OpenAI(api_key=api_key)

    if args.property:
        targets = [args.property]
    else:
        targets = [pid for pid in profiles if pid not in output]

    print(f"Properties to process : {len(targets)}")
    print(f"Concurrent workers    : {args.workers}\n")

    done = 0

    def _run(pid):
        result = process_property(pid, profiles[pid], client)
        return pid, result

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_run, pid): pid for pid in targets}

        for future in as_completed(futures):
            pid, result = future.result()
            done += 1

            if args.property:
                print(json.dumps({pid: result}, indent=2))
                continue

            if result:
                output[pid] = result
            else:
                # Mark as processed even if empty so we don't retry it
                output[pid] = {}

            with open(OUTPUT_PATH, "w") as f:
                json.dump(output, f, indent=2)

            amenity_count = len(result)
            print(f"  [{done}/{len(targets)}] {pid[:8]}… — {amenity_count} amenities with reasons")

    if not args.property:
        non_empty = sum(1 for v in output.values() if v)
        print(f"\nDone. {non_empty}/{len(output)} properties had consolidatable reasons.")
        print(f"Output written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
