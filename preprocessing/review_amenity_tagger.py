"""
review_amenity_tagger.py

Given a review and its property ID, returns a 1/0 for every amenity listed
at that property indicating whether the review text mentions it.

Core function:
    tag_review(property_id, review_text, desc_rows) -> dict[str, int]

Can also be run directly to demo on a sample of real reviews:
    OPENAI_API_KEY=sk-... python review_amenity_tagger.py
"""

import csv
import json
import os
import sys
from openai import OpenAI
from amenity_normalizer import normalize_amenities

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.abspath(__file__))
DESC_PATH = os.path.join(BASE, "../sources/Description_PROC.csv")
REV_PATH  = os.path.join(BASE, "../sources/Reviews_PROC.csv")

# MODEL = "gpt-4o-mini"
MODEL = "gpt-4o"

TAXONOMY_PATH = os.path.join(BASE, "amenity_taxonomy.json")


def load_taxonomy() -> dict:
    """Load amenity_taxonomy.json if it exists, else return empty dict."""
    if os.path.exists(TAXONOMY_PATH):
        with open(TAXONOMY_PATH) as f:
            return json.load(f)
    return {}


# Load once at import time
_TAXONOMY = load_taxonomy()

# All fields that contain amenity lists
AMENITY_FIELDS = [
    "popular_amenities_list",
    "property_amenity_accessibility",
    "property_amenity_activities_nearby",
    "property_amenity_business_services",
    "property_amenity_conveniences",
    "property_amenity_family_friendly",
    "property_amenity_food_and_drink",
    "property_amenity_guest_services",
    "property_amenity_internet",
    "property_amenity_langs_spoken",
    "property_amenity_more",
    "property_amenity_outdoor",
    "property_amenity_parking",
    "property_amenity_spa",
    "property_amenity_things_to_do",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_json_field(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return []
    try:
        val = json.loads(raw)
        return [str(v) for v in val] if isinstance(val, list) else []
    except json.JSONDecodeError:
        return []


def get_property_amenities(property_id: str, desc_rows: list[dict]) -> list[str]:
    """
    Returns a flat, deduplicated list of every amenity item listed for a property,
    drawn from all amenity fields in Description_PROC.
    """
    row = next((r for r in desc_rows if r["eg_property_id"] == property_id), None)
    if row is None:
        return []

    seen = set()
    amenities = []
    for field in AMENITY_FIELDS:
        for item in parse_json_field(row.get(field, "")):
            item = item.strip()
            if item and item.lower() not in seen:
                seen.add(item.lower())
                amenities.append(item)
    return amenities


# ── Core function ─────────────────────────────────────────────────────────────

def tag_review(
    property_id: str,
    review_text: str,
    desc_rows: list[dict],
    client: OpenAI,
    use_taxonomy: bool = True,
) -> dict[str, int]:
    """
    For a single review, returns {amenity: 1 or 0} for every amenity
    listed at the corresponding property.

    Uses one LLM call to handle semantic matching
    (e.g. "the jacuzzi was great" -> hot_tub = 1).
    """
    raw_amenities = get_property_amenities(property_id, desc_rows)
    amenities = normalize_amenities(raw_amenities) if use_taxonomy else raw_amenities
    if not amenities:
        return {}
    if not review_text or not review_text.strip():
        return {a: 0 for a in amenities}

    amenity_list_str = "\n".join(f"- {a}" for a in amenities)

    prompt = f"""You are analyzing a hotel guest review to determine which amenities are mentioned.

AMENITIES AT THIS PROPERTY:
{amenity_list_str}

GUEST REVIEW:
\"\"\"{review_text.strip()}\"\"\"

TASK: For each amenity listed above, output 1 if the review mentions or clearly references it
(even indirectly — e.g. "the jacuzzi" counts for "hot tub"), or 0 if it does not.

Respond with ONLY a JSON object mapping each amenity exactly as written to 1 or 0.
No explanation, no markdown:
{{"amenity name": 0 or 1, ...}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        # Enforce 0/1 integers and ensure every amenity has an entry
        return {a: int(bool(result.get(a, 0))) for a in amenities}

    except Exception as e:
        print(f"  [LLM error] {e}", file=sys.stderr)
        return {a: 0 for a in amenities}  # noqa: F821


# ── Detail scoring ───────────────────────────────────────────────────────────

def score_amenity_detail(
    property_id: str,
    review_text: str,
    desc_rows: list[dict],
    client: OpenAI,
    use_taxonomy: bool = True,
) -> dict[str, int]:
    """
    For a single review, returns {amenity: detail_score} for every amenity
    listed at the corresponding property.

    detail_score:
        0     — amenity not mentioned in the review
        1–3   — passing mention only ("the pool was nice")
        4–6   — some description: a specific observation or two
        7–10  — detailed: multiple specific observations, reasoning for why
                the amenity was good/bad, comparisons, or vivid description

    Uses one LLM call for all amenities at the property.
    """
    raw_amenities = get_property_amenities(property_id, desc_rows)
    amenities = normalize_amenities(raw_amenities) if use_taxonomy else raw_amenities
    if not amenities:
        return {}
    if not review_text or not review_text.strip():
        return {a: 0 for a in amenities}

    amenity_list_str = "\n".join(f"- {a}" for a in amenities)

    prompt = f"""You are analyzing a hotel guest review to score how much detail it provides about each amenity.

AMENITIES AT THIS PROPERTY:
{amenity_list_str}

GUEST REVIEW:
\"\"\"{review_text.strip()}\"\"\"

TASK: For each amenity, assign an integer detail score 0–10 using this scale:
  0   — not mentioned at all
  1–3 — passing mention, no real description (e.g. "the pool was good", "great wifi")
  4–6 — some description: at least one specific observation (e.g. "the pool was clean and not crowded")
  7–9 — detailed: multiple specific observations, or reasoning for why it was good/bad
        (e.g. "the pool was heated, well-maintained, and had a shallow end for kids")
  10  — exceptionally thorough: vivid multi-sentence description with specifics, comparisons,
        or strong reasoning (e.g. "there were two outdoor pools and a hot tub, the water was
        crystal clear, a poolside bar was open until midnight, and the staff kept towels stocked")

Semantic matching applies — "jacuzzi" counts for "hot tub".

Respond with ONLY a JSON object mapping each amenity exactly as written to its integer score.
No explanation, no markdown:
{{"amenity name": 0–10, ...}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        # Clamp to 0–10 and ensure every amenity has an entry
        return {a: max(0, min(10, int(result.get(a, 0)))) for a in amenities}

    except Exception as e:
        print(f"  [LLM error] {e}", file=sys.stderr)
        return {a: 0 for a in amenities}


# ── Demo ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY environment variable.")
    client = OpenAI(api_key=api_key)

    desc_rows = load_csv(DESC_PATH)
    rev_rows  = load_csv(REV_PATH)

    # Pick a few sample reviews that have text, across different properties
    samples = [r for r in rev_rows if (r.get("review_text") or "").strip()][:5]

    for r in samples:
        prop_id     = r["eg_property_id"]
        review_text = r["review_text"].strip()
        date        = r.get("acquisition_date", "")

        # Find city name for display
        desc = next((d for d in desc_rows if d["eg_property_id"] == prop_id), {})
        city = desc.get("city", prop_id[:8])

        print(f"\n{'='*60}")
        print(f"Property : {city}")
        print(f"Date     : {date}")
        print(f"Review   : {review_text[:120]}{'...' if len(review_text) > 120 else ''}")
        print()

        tags = tag_review(prop_id, review_text, desc_rows, client)

        mentioned     = {a: v for a, v in tags.items() if v == 1}
        not_mentioned = {a: v for a, v in tags.items() if v == 0}

        print(f"Mentioned ({len(mentioned)}/{len(tags)}):")
        for a in mentioned:
            print(f"  [1] {a}")
        print(f"\nNot mentioned ({len(not_mentioned)}/{len(tags)}):")
        for a in list(not_mentioned)[:10]:   # cap so output stays readable
            print(f"  [0] {a}")
        if len(not_mentioned) > 10:
            print(f"  ... and {len(not_mentioned) - 10} more")


if __name__ == "__main__":
    main()
