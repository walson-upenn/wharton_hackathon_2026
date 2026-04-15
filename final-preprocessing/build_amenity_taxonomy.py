"""
build_amenity_taxonomy.py

One-time preprocessing script. Collects every unique amenity string across
all properties, then asks GPT to:
  1. Prune items a guest would never naturally mention in a review
     (measurements, policy statements, certifications, eco-labels)
  2. Consolidate overlapping items into canonical group names
     (massage - deep-tissue / massage - prenatal / massage - sports → "massage")

Outputs: amenity_taxonomy.json
  {
    "original amenity string": "canonical group name",  <- kept & grouped
    "elevator door width (inches): 36": null,           <- pruned
    ...
  }

The tagger loads this file and maps amenities before sending them to the LLM,
so it only ever works with a clean, deduplicated set.

Usage:
    OPENAI_API_KEY=sk-... python build_amenity_taxonomy.py
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "../preprocessing"))

from openai import OpenAI
from review_amenity_tagger import load_csv, parse_json_field, AMENITY_FIELDS

BASE        = _HERE
DESC_PATH   = os.path.join(BASE, "../sources/Description_PROC.csv")
# Write to preprocessing/ so amenity_normalizer.py can find it at its expected path
OUTPUT_PATH = os.path.join(BASE, "../preprocessing/amenity_taxonomy.json")

MODEL = "gpt-4o"   # use the stronger model — this runs once and quality matters


def collect_all_amenities(desc_rows: list[dict]) -> list[str]:
    """Flat deduplicated list of every amenity string across all properties."""
    seen = set()
    result = []
    for row in desc_rows:
        for field in AMENITY_FIELDS:
            for item in parse_json_field(row.get(field, "")):
                item = item.strip()
                if item and item.lower() not in seen:
                    seen.add(item.lower())
                    result.append(item)
    return sorted(result)


def build_taxonomy(amenities: list[str], client: OpenAI) -> dict[str, str | None]:
    amenity_block = "\n".join(f"- {a}" for a in amenities)

    prompt = f"""You are building a clean amenity taxonomy for a hotel review analysis system.

Below is a raw list of hotel amenity strings scraped from property listings.
Many are too technical, too specific, or too obscure for a guest to ever mention
in a free-text review. Others are redundant variants of the same concept.

Your task: for each amenity string, decide one of:
  A) PRUNE  — a guest would never naturally mention this in a review.
              Examples: measurements ("elevator door width (inches): 36"),
              eco-certifications ("at least 80% lighting from leds"),
              policy statements ("if you have requests for specific accessibility needs..."),
              supply-chain details ("biodegradable coffee stirrers"),
              language spoken ("english", "spanish")
  B) KEEP   — assign a clean canonical group name (lowercase, concise).
              Merge overlapping items: "massage - deep-tissue", "massage - prenatal",
              "massage - sports" all become "massage".
              "available in all rooms: free wifi" and "in-room wifi speed: 25+ mbps"
              both become "wifi".

Return ONLY a valid JSON object — no explanation, no markdown:
{{
  "original string": "canonical name or null if pruned",
  ...
}}

AMENITY LIST:
{amenity_block}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY environment variable.")
    client = OpenAI(api_key=api_key)

    desc_rows = load_csv(DESC_PATH)
    amenities = collect_all_amenities(desc_rows)
    print(f"Collected {len(amenities)} unique amenity strings across all properties.")

    print("Calling GPT to build taxonomy…")
    taxonomy = build_taxonomy(amenities, client)

    kept    = {k: v for k, v in taxonomy.items() if v is not None}
    pruned  = {k for k, v in taxonomy.items() if v is None}
    unique_canonical = set(kept.values())

    print(f"\nResults:")
    print(f"  {len(kept)} kept  →  {len(unique_canonical)} unique canonical groups")
    print(f"  {len(pruned)} pruned")

    # Show a sample of what got pruned and what got merged
    print(f"\nSample pruned:")
    for a in sorted(pruned)[:10]:
        print(f"  ✗  {a}")

    print(f"\nSample merges (original → canonical):")
    from collections import defaultdict
    groups = defaultdict(list)
    for orig, canon in kept.items():
        groups[canon].append(orig)
    merged = {k: v for k, v in groups.items() if len(v) > 1}
    for canon, originals in sorted(merged.items())[:10]:
        print(f"  '{canon}':")
        for o in originals:
            print(f"      ← {o}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)
    print(f"\nWrote taxonomy → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
