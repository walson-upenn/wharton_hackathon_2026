"""
amenity_normalizer.py

Loads amenity_taxonomy.json and normalizes raw amenity strings to clean
canonical labels before they are sent to the LLM.

    "full breakfast available for a fee 6:30 am–11:00 am..." -> "breakfast"
    "available in all rooms: free wifi"                       -> "wifi"
    "massage - deep-tissue"                                   -> "massage"

If amenity_taxonomy.json hasn't been built yet, normalize() is a no-op
and raw strings pass through unchanged.

Usage:
    from amenity_normalizer import normalize_amenities

    clean = normalize_amenities(raw_list)
    # clean is a deduplicated list of canonical names, with pruned items removed
"""

import json
import os

TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "amenity_taxonomy.json")


def _load() -> dict:
    if os.path.exists(TAXONOMY_PATH):
        with open(TAXONOMY_PATH) as f:
            return json.load(f)
    return {}


_TAXONOMY = _load()


def normalize_amenities(raw: list[str]) -> list[str]:
    """
    Map a list of raw amenity strings to clean canonical names.
    - Items mapped to null in the taxonomy are dropped (pruned).
    - Items not in the taxonomy pass through unchanged.
    - Duplicates after mapping are collapsed.
    Returns a deduplicated ordered list.
    """
    if not _TAXONOMY:
        return raw

    seen = set()
    result = []
    for item in raw:
        key   = item.strip()
        canon = _TAXONOMY.get(key, key)    # strip whitespace; unknown strings pass through
        if canon is None:
            continue                        # pruned
        if canon.lower() not in seen:
            seen.add(canon.lower())
            result.append(canon)
    return result
