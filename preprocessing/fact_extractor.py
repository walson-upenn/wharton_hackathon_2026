"""
fact_extractor.py

For a given property, extracts specific facts stated about each amenity
across all of its reviews. One LLM call per review — returns a dict of
{amenity: [fact, fact, ...]} per review, then aggregates across the property.

Run:
    OPENAI_API_KEY=sk-... python fact_extractor.py [property_id]

If no property_id is given, picks the first property that has at least 5 reviews.
"""

import csv
import json
import os
import sys
from collections import defaultdict
from openai import OpenAI

from review_amenity_tagger import load_csv, get_property_amenities
from amenity_normalizer import normalize_amenities

BASE      = os.path.dirname(os.path.abspath(__file__))
DESC_PATH = os.path.join(BASE, "../sources/Description_PROC.csv")
REV_PATH  = os.path.join(BASE, "../sources/Reviews_PROC.csv")

MODEL = "gpt-4o-mini"


def extract_facts_from_review(
    review_text: str,
    amenities: list[str],
    client: OpenAI,
) -> dict[str, list[str]]:
    """
    Given a review and the list of amenities at a property, returns
    {amenity: [fact, ...]} for every amenity the review says something
    concrete about. Amenities not meaningfully mentioned are omitted.

    Facts should be short, specific, and verifiable — not sentiment.
    e.g. "pool": ["heated", "two pools", "open until 10pm", "swim-up bar"]
    NOT: "pool": ["great", "loved it"]
    """
    amenity_list_str = "\n".join(f"- {a}" for a in amenities)

    prompt = f"""You are extracting specific facts from a hotel guest review.

AMENITIES AT THIS PROPERTY:
{amenity_list_str}

GUEST REVIEW:
\"\"\"{review_text.strip()}\"\"\"

TASK: For each amenity that the review says something concrete and specific about,
list the distinct facts stated. A fact must be specific and verifiable — not just
sentiment or vague praise.

INCLUDE: "heated", "two pools", "open until 10pm", "free", "slow in the lobby"
EXCLUDE: "great", "loved it", "nice", "good", "bad", "disappointing"

Omit amenities the review doesn't mention, or only praises/criticises vaguely.

Respond with ONLY a JSON object. Each key is an amenity name exactly as written
above, and each value is a list of short fact strings (3–8 words each).
No explanation, no markdown:
{{"amenity": ["fact", "fact"], ...}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        # Keep only amenities we recognise and non-empty fact lists
        return {
            a: [str(f) for f in facts if str(f).strip()]
            for a, facts in result.items()
            if a in amenities and isinstance(facts, list) and facts
        }
    except Exception as e:
        print(f"  [LLM error] {e}", file=sys.stderr)
        return {}


def extract_facts_for_property(
    property_id: str,
    desc_rows: list[dict],
    rev_rows: list[dict],
    client: OpenAI,
) -> dict[str, list[str]]:
    """
    Runs fact extraction over every review for a property and returns
    aggregated facts per amenity: {amenity: [deduped facts across all reviews]}.
    """
    amenities = normalize_amenities(get_property_amenities(property_id, desc_rows))
    if not amenities:
        print(f"No amenities found for {property_id}", file=sys.stderr)
        return {}

    reviews = [
        r for r in rev_rows
        if r["eg_property_id"] == property_id
        and (r.get("review_text") or "").strip()
    ]
    if not reviews:
        print(f"No reviews found for {property_id}", file=sys.stderr)
        return {}

    print(f"Property : {property_id}")
    print(f"Amenities: {len(amenities)}")
    print(f"Reviews  : {len(reviews)}")
    print()

    aggregated: dict[str, list[str]] = defaultdict(list)

    for i, r in enumerate(reviews):
        text = r["review_text"].strip()
        print(f"  [{i+1}/{len(reviews)}] {text[:80]}{'...' if len(text) > 80 else ''}")
        facts = extract_facts_from_review(text, amenities, client)
        for amenity, amenity_facts in facts.items():
            aggregated[amenity].extend(amenity_facts)

    # Deduplicate facts per amenity (case-insensitive)
    deduped = {}
    for amenity, facts in aggregated.items():
        seen = set()
        unique = []
        for f in facts:
            key = f.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(f)
        deduped[amenity] = unique

    return deduped


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY environment variable.")

    client    = OpenAI(api_key=api_key)
    desc_rows = load_csv(DESC_PATH)
    rev_rows  = load_csv(REV_PATH)

    # Pick property_id from args or find a property with enough reviews to be interesting
    if len(sys.argv) > 1:
        property_id = sys.argv[1]
    else:
        from collections import Counter
        counts = Counter(r["eg_property_id"] for r in rev_rows if (r.get("review_text") or "").strip())
        property_id = next(pid for pid, n in counts.most_common() if n >= 5)
        print(f"No property_id given — using {property_id} ({counts[property_id]} reviews)\n")

    facts = extract_facts_for_property(property_id, desc_rows, rev_rows, client)

    print(f"\n{'='*60}")
    print("AGGREGATED FACTS PER AMENITY")
    print('='*60)
    for amenity, amenity_facts in sorted(facts.items(), key=lambda x: -len(x[1])):
        print(f"\n{amenity} ({len(amenity_facts)} facts):")
        for f in amenity_facts:
            print(f"  • {f}")

    amenities_with_facts = set(facts.keys())
    all_amenities = set(normalize_amenities(get_property_amenities(property_id, desc_rows)))
    silent = all_amenities - amenities_with_facts
    if silent:
        print(f"\n{'='*60}")
        print(f"AMENITIES WITH NO FACTS EXTRACTED ({len(silent)}):")
        for a in sorted(silent):
            print(f"  – {a}")


if __name__ == "__main__":
    main()
