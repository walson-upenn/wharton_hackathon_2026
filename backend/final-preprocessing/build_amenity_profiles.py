"""
build_amenity_profiles.py

For each property, ranks its amenities by importance using prompt_rank_importance.
One LLM call per property — much faster than build_review_profiles.py.

Output structure (amenity_profiles.json):
    {
        "<property_id>": {
            "<amenity>": <float in [0.0, 1.0]>
        },
        ...
    }

Scoring: the LLM returns a strict ordered list of all amenities from most to least
important. Scores are assigned by normalized rank position:
    rank 0 (most important)    → 1.0
    rank n-1 (least important) → 0.0
    all others                 → 1 - rank / (n - 1)   (linear interpolation)

This replaces the old four-tier approach (critical=1.0, important=0.67, moderate=0.33,
minor=0.0) with a smooth continuous scale that eliminates hard score jumps between
neighbouring amenities.

Resumable: properties already present in the output file are skipped.

Run:
    OPENAI_API_KEY=sk-... python build_amenity_profiles.py [--workers N] [--property <id>]

    --workers N       concurrent properties (default: 20)
    --property <id>   process a single property and print result (for testing)

    --rerank          re-normalize the existing amenity_profiles.json in-place using
                      the new rank-based formula, without making any LLM calls.
                      Use this to migrate pre-existing tier-scored data.
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "../preprocessing"))

from openai import OpenAI
from review_amenity_tagger import load_csv, get_property_amenities
from amenity_normalizer import normalize_amenities
from amenity_prompts import prompt_rank_importance
from gap_score_components import _build_property_description

BASE        = _HERE
DESC_PATH   = os.path.join(BASE, "../sources/Description_PROC.csv")
OUTPUT_PATH = os.path.join(BASE, "amenity_profiles.json")


def process_property(pid: str, desc_rows: list[dict], client: OpenAI) -> dict[str, float]:
    """Resolves amenities, builds description, calls prompt_rank_importance."""
    amenities   = normalize_amenities(get_property_amenities(pid, desc_rows))
    description = _build_property_description(pid, desc_rows)
    return prompt_rank_importance(amenities, description, client)


def _rerank_existing():
    """
    Re-normalize an existing tier-scored amenity_profiles.json in-place.
    Sorts each property's amenities by their current score (desc), breaks
    ties alphabetically, then assigns rank-normalized [0,1] scores.
    No LLM calls required.
    """
    if not os.path.exists(OUTPUT_PATH):
        sys.exit(f"No file to rerank: {OUTPUT_PATH}")

    with open(OUTPUT_PATH) as f:
        profiles = json.load(f)

    print(f"Reranking {len(profiles)} properties in {OUTPUT_PATH} …")
    new_profiles = {}
    for prop_id, amenity_scores in profiles.items():
        if not amenity_scores:
            new_profiles[prop_id] = {}
            continue
        ranked = sorted(amenity_scores.items(), key=lambda kv: (-kv[1], kv[0]))
        n = len(ranked)
        new_profiles[prop_id] = {
            amenity: (1.0 if n == 1 else round(1.0 - rank / (n - 1), 4))
            for rank, (amenity, _) in enumerate(ranked)
        }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(new_profiles, f, indent=2)

    all_scores = [s for p in new_profiles.values() for s in p.values()]
    print(f"Done. Score range: {min(all_scores):.4f} – {max(all_scores):.4f}  "
          f"({len(set(round(s,4) for s in all_scores))} unique values across "
          f"{len(all_scores)} amenity-entries)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers",  type=int, default=20,   help="concurrent properties (default: 20)")
    parser.add_argument("--property", type=str, default=None, help="process a single property (for testing)")
    parser.add_argument("--rerank",   action="store_true",    help="re-normalize existing file in-place (no LLM calls)")
    args = parser.parse_args()

    if args.rerank:
        _rerank_existing()
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY environment variable.")

    client    = OpenAI(api_key=api_key)
    desc_rows = load_csv(DESC_PATH)
    prop_lookup = {r["eg_property_id"]: r for r in desc_rows}

    # Load existing output for resumption
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            output = json.load(f)
        print(f"Resuming — {len(output)} properties already done.")
    else:
        output = {}

    # Determine targets
    all_pids = list(prop_lookup.keys())
    if args.property:
        targets = [args.property]
    else:
        targets = [pid for pid in all_pids if pid not in output]

    print(f"Properties to process : {len(targets)}")
    print(f"Concurrent workers    : {args.workers}\n")

    done = 0

    def _run(pid):
        scores = process_property(pid, desc_rows, client)
        return pid, scores

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_run, pid): pid for pid in targets}

        for future in as_completed(futures):
            pid, scores = future.result()
            done += 1
            city = prop_lookup.get(pid, {}).get("city", pid[:8])

            if args.property:
                print(json.dumps({pid: scores}, indent=2))
            else:
                output[pid] = scores
                with open(OUTPUT_PATH, "w") as f:
                    json.dump(output, f, indent=2)
                print(f"  [{done}/{len(targets)}] {city} ({pid[:8]}…) — "
                      f"{len(scores)} amenities ranked")

    if not args.property:
        print(f"\nDone. Output written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
