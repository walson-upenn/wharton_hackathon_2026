"""
amenity_prompts.py

All LLM prompting functions for amenity analysis. Each function takes a
pre-resolved amenity list so callers control normalization (raw vs. taxonomy).

Functions:
    prompt_tag_mentioned    — 0/1 per amenity: is it mentioned in the review?
    prompt_score_sentiment  — [-1, 1] per mentioned amenity: sentiment
    prompt_score_detail     — [0, 4] per amenity: how much concrete detail?
    prompt_rank_importance  — [0, 1] per amenity: how important to this property?
"""

import json
import sys
from openai import OpenAI

MODEL = "gpt-4o-mini"


def _strip_fences(raw: str) -> str:
    """Strip markdown code fences from an LLM response."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ── 1. Mention tagging ────────────────────────────────────────────────────────

def prompt_tag_mentioned(
    review_text: str,
    amenities: list[str],
    client: OpenAI,
) -> dict[str, int]:
    """
    Returns {amenity: 1 or 0} for every amenity in the list.

    1 = review mentions or clearly references the amenity (semantic matching
        applies — "jacuzzi" counts for "hot tub").
    0 = not mentioned.
    """
    if not review_text.strip():
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
        result = json.loads(_strip_fences(response.choices[0].message.content))
        return {a: int(bool(result.get(a, 0))) for a in amenities}
    except Exception as e:
        print(f"  [LLM error] prompt_tag_mentioned: {e}", file=sys.stderr)
        return {a: 0 for a in amenities}


# ── 2. Sentiment scoring ──────────────────────────────────────────────────────

# Valence + intensity flags map to float scores:
#   positive + strong  →  1.0
#   positive + weak    →  0.5
#   neutral            →  0.0
#   negative + weak    → -0.5
#   negative + strong  → -1.0
#
# The model picks from small enums — no arbitrary numbers, no bleed from
# overall review tone into individual amenity scores.

_SENTIMENT_MAP = {
    ("positive", "strong"):  1.0,
    ("positive", "weak"):    0.5,
    ("neutral",  "strong"):  0.0,
    ("neutral",  "weak"):    0.0,
    ("negative", "weak"):   -0.5,
    ("negative", "strong"): -1.0,
}

def prompt_score_sentiment(
    review_text: str,
    amenities: list[str],
    client: OpenAI,
) -> dict[str, float]:
    """
    Returns {amenity: sentiment} for amenities mentioned in the review.
    Score is in [-1.0, 1.0]:
        -1.0 = strongly negative   ("the pool was filthy and freezing")
        -0.5 = mildly negative     ("the wifi was a bit slow")
         0.0 = neutral / mixed     ("the pool was okay, nothing special")
        +0.5 = mildly positive     ("the wifi worked fine")
        +1.0 = strongly positive   ("the pool was immaculate and heated")

    Sentiment is scoped to what the review says about that specific amenity —
    not the overall tone of the review. A review can be positive overall but
    negative about a specific amenity, and vice versa.

    Amenities not mentioned are omitted from the output.
    """
    if not review_text.strip():
        return {}

    amenity_list_str = "\n".join(f"- {a}" for a in amenities)

    prompt = f"""You are analyzing the sentiment a hotel guest expresses toward specific amenities.

AMENITIES AT THIS PROPERTY:
{amenity_list_str}

GUEST REVIEW:
\"\"\"{review_text.strip()}\"\"\"

For each amenity the review mentions, classify the sentiment expressed toward
THAT SPECIFIC AMENITY — not the review's overall tone.

For example: "The pool was disgusting but the staff were incredible" →
  pool sentiment = negative/strong, staff sentiment = positive/strong

For each mentioned amenity provide two fields:

  valence   — "positive", "negative", or "neutral"
              neutral = mixed, ambiguous, or purely factual with no clear feeling

  intensity — "strong" or "weak"
              strong = clearly emphatic ("filthy", "immaculate", "incredibly slow")
              weak   = mild or hedged ("fine", "a bit slow", "decent", "okay")

Omit amenities the review does not mention at all.
Semantic matching applies: "jacuzzi" counts for "hot tub".

Respond with ONLY a JSON object. Each key is an amenity name exactly as written above.
No explanation, no markdown:
{{"amenity name": {{"valence": "positive|negative|neutral", "intensity": "strong|weak"}}, ...}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        result = json.loads(_strip_fences(response.choices[0].message.content))

        scores = {}
        for a in amenities:
            if a not in result:
                continue
            flags    = result[a]
            valence  = str(flags.get("valence",  "neutral")).lower()
            intensity = str(flags.get("intensity", "weak")).lower()
            if valence not in ("positive", "negative", "neutral"):
                valence = "neutral"
            if intensity not in ("strong", "weak"):
                intensity = "weak"
            scores[a] = _SENTIMENT_MAP[(valence, intensity)]
        return scores

    except Exception as e:
        print(f"  [LLM error] prompt_score_sentiment: {e}", file=sys.stderr)
        return {}


# ── 2b. Reason extraction ────────────────────────────────────────────────────

def prompt_extract_reason(
    review_text: str,
    amenity_sentiments: dict[str, float],
    client: OpenAI,
) -> dict[str, list[str] | None]:
    """
    For each non-neutral amenity in amenity_sentiments, extracts all distinct
    reasons the guest gave for their sentiment.

    Returns {amenity: [reason, ...]} where:
        - Each reason is a concise, specific phrase drawn from the review text
        - An empty list or null means the review expressed sentiment but gave
          no concrete reasons — a meaningful gap signal in itself

    Only non-neutral amenities should be passed in (filter out 0.0 scores before calling).
    """
    if not review_text.strip() or not amenity_sentiments:
        return {}

    lines = []
    for amenity, score in amenity_sentiments.items():
        direction = "positive" if score > 0 else "negative"
        lines.append(f"- {amenity} ({direction})")
    amenity_lines = "\n".join(lines)

    prompt = f"""You are extracting the specific reasons a hotel guest felt positively or negatively about certain amenities.

GUEST REVIEW:
\"\"\"{review_text.strip()}\"\"\"

AMENITIES WITH KNOWN SENTIMENT:
{amenity_lines}

For each amenity, extract ALL distinct reasons from the review that explain the sentiment.
Each reason must come directly from the review text — do not infer or assume.

A valid reason is a concrete, specific phrase (under 15 words):
  GOOD: "dirty and had a strong chlorine smell", "heated and open until midnight", "slow during peak hours"
  NOT VALID: "bad", "not good", "guest was unhappy", "positive experience"

If the review expresses sentiment about an amenity but gives no concrete reason
(e.g. "the pool was amazing!" with nothing else said about it), return an empty list.

Respond with ONLY a JSON object. Each key is an amenity name exactly as written above,
each value is a list of reason strings (may be empty).
No explanation, no markdown:
{{"amenity name": ["reason 1", "reason 2"] or [], ...}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0,
        )
        result = json.loads(_strip_fences(response.choices[0].message.content))

        reasons = {}
        for amenity in amenity_sentiments:
            raw = result.get(amenity)
            if isinstance(raw, list):
                reasons[amenity] = [r.strip() for r in raw if isinstance(r, str) and r.strip()]
            else:
                reasons[amenity] = []
        return reasons

    except Exception as e:
        print(f"  [LLM error] prompt_extract_reason: {e}", file=sys.stderr)
        return {a: [] for a in amenity_sentiments}


# ── 3. Detail scoring ─────────────────────────────────────────────────────────

# Criteria the model evaluates as binary flags. Score = number of flags set.
#
#   mentioned  (1) — amenity is referenced at all (semantic matching applies)
#   specific   (1) — at least one concrete, verifiable attribute is stated
#                    ("heated", "free", "slow", "two pools") — NOT "great"/"nice"
#   multiple   (1) — more than one distinct attribute, OR a clear reason given
#                    for the rating ("crowded because of the conference")
#   rich       (1) — goes further: comparisons, quantities, time/context
#                    ("open until 10pm", "better than the one at Hotel X",
#                     "crowded on weekends but quiet after noon")
#
# Final score 0–4 maps to:   0 = not mentioned
#                             1 = vague mention
#                             2 = some detail
#                             3 = good detail
#                             4 = thorough

DETAIL_CRITERIA = ["mentioned", "specific", "multiple", "rich"]

def prompt_score_detail(
    review_text: str,
    amenities: list[str],
    client: OpenAI,
) -> dict[str, int]:
    """
    Returns {amenity: detail_score} in [0, 4] for every amenity in the list.

    Score is the sum of four binary criteria — the model never picks a number,
    it only answers yes/no per criterion, eliminating arbitrary within-band choices:

        0  not mentioned
        1  vague mention only ("the pool was nice", "great wifi")
        2  at least one specific, verifiable attribute stated
        3  multiple distinct attributes or a clear reason given
        4  rich detail — comparisons, quantities, time/context clues
    """
    if not review_text.strip():
        return {a: 0 for a in amenities}

    amenity_list_str = "\n".join(f"- {a}" for a in amenities)

    prompt = f"""You are analyzing a hotel guest review. For each amenity, answer four yes/no questions.

AMENITIES AT THIS PROPERTY:
{amenity_list_str}

GUEST REVIEW:
\"\"\"{review_text.strip()}\"\"\"

For each amenity, answer these four questions with 1 (yes) or 0 (no):

  mentioned — does the review reference this amenity at all?
              (semantic matching applies: "jacuzzi" counts for "hot tub")

  specific  — does the review state at least one concrete, verifiable attribute?
              COUNTS: "heated", "free", "slow", "two pools", "on the 3rd floor"
              DOES NOT COUNT: "great", "nice", "amazing", "loved it", "bad"

  multiple  — does the review give more than one distinct concrete attribute,
              OR provide a clear reason for the rating?
              ("the pool was clean but crowded" = yes — two attributes
               "wifi was slow because the hotel was full" = yes — reason given)

  rich      — does the review go further with comparisons, quantities, or context?
              ("open until 10pm", "better than most hotels", "two outdoor pools
               and a hot tub", "crowded on weekends but quiet after noon")

Rules:
- Each criterion builds on the last. If "mentioned" = 0, all others must also be 0.
- If "specific" = 0, then "multiple" and "rich" must also be 0.
- If "multiple" = 0, then "rich" must also be 0.

Respond with ONLY a JSON object. Each key is an amenity name exactly as written above,
and each value is an object with the four criteria as keys, each 0 or 1.
No explanation, no markdown:
{{"amenity name": {{"mentioned": 0, "specific": 0, "multiple": 0, "rich": 0}}, ...}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        result = json.loads(_strip_fences(response.choices[0].message.content))

        scores = {}
        for a in amenities:
            flags = result.get(a, {})
            scores[a] = sum(int(bool(flags.get(c, 0))) for c in DETAIL_CRITERIA)
        return scores

    except Exception as e:
        print(f"  [LLM error] prompt_score_detail: {e}", file=sys.stderr)
        return {a: 0 for a in amenities}


# ── 4. Amenity importance ranking ─────────────────────────────────────────────

def prompt_rank_importance(
    amenities: list[str],
    property_description: str,
    client: OpenAI,
) -> dict[str, float]:
    """
    Returns {amenity: importance_score} in [0.0, 1.0] for every amenity
    in the list (already pruned via amenity_taxonomy.json).

    The LLM returns a strict ordered list of all amenities from most to least
    important. Scores are then assigned by normalized rank position:
        rank 0 (most important)  → 1.0
        rank n-1 (least important) → 0.0
        all others               → 1 - rank / (n-1)   (linear interpolation)

    This eliminates the hard tier jumps of the previous categorical approach
    (1.0 / 0.67 / 0.33 / 0.0) while preserving the full ordering signal from
    the LLM.

    Combines two signals:
      A. General heuristics — amenities that matter most to the average traveler
         regardless of property type (wifi, breakfast, parking tend to rank high;
         obscure conveniences tend to rank low)
      B. Property-specific importance — inferred from the property description
         (a water-park resort → pool tops the list; a budget hostel → free wifi
         outranks concierge)
    """
    if not amenities:
        return {}

    if len(amenities) == 1:
        return {amenities[0]: 1.0}

    amenity_list_str = "\n".join(f"- {a}" for a in amenities)

    prompt = f"""You are assessing how important each amenity is to guests considering this specific hotel.

PROPERTY DESCRIPTION:
\"\"\"{property_description.strip()}\"\"\"

AMENITIES (already filtered to guest-relevant items):
{amenity_list_str}

Rank ALL of the amenities above from MOST important to LEAST important for this specific property,
combining two factors:

  A. GENERAL IMPORTANCE — how much does this amenity type matter to the average traveler?
     High by default: wifi, breakfast, pool, parking, air conditioning, gym
     Low by default: languages spoken, niche business services, minor conveniences

  B. PROPERTY-SPECIFIC IMPORTANCE — does this property's identity or description
     make this amenity especially central or irrelevant?
     Examples:
       - A resort with a water park → pool near the top; business services near the bottom
       - A city centre business hotel → parking higher; outdoor activities lower
       - A spa retreat → spa at the top; newspapers at the bottom
       - A budget hostel → free wifi at the top; concierge at the bottom

Rules:
  - Include EVERY amenity exactly once
  - Use the exact amenity strings as written above
  - No ties — give a strict ranking from 1st (most important) to last (least important)

Respond with ONLY a JSON array of amenity name strings, ordered from most to least important.
No explanation, no markdown:
["most important amenity", "second most important", ..., "least important amenity"]"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        ranked_list = json.loads(_strip_fences(response.choices[0].message.content))

        if not isinstance(ranked_list, list):
            raise ValueError("Expected a JSON array")

        # Build a position lookup; amenities not in the response get appended at the end
        position: dict[str, int] = {}
        for i, name in enumerate(ranked_list):
            if isinstance(name, str) and name in {a for a in amenities}:
                if name not in position:
                    position[name] = i

        # Fill any missing amenities at the end (shouldn't happen with a correct model response)
        next_pos = len(ranked_list)
        for a in amenities:
            if a not in position:
                position[a] = next_pos
                next_pos += 1

        # Normalize: rank 0 → 1.0, rank n-1 → 0.0
        n = len(amenities)
        sorted_amenities = sorted(amenities, key=lambda a: position[a])
        scores = {}
        for rank, a in enumerate(sorted_amenities):
            scores[a] = round(1.0 - rank / (n - 1), 4)
        return scores

    except Exception as e:
        print(f"  [LLM error] prompt_rank_importance: {e}", file=sys.stderr)
        # Fallback: uniform spacing
        n = len(amenities)
        return {a: round(1.0 - i / (n - 1), 4) for i, a in enumerate(amenities)}


# ── 5. Reason consolidation ───────────────────────────────────────────────────

def prompt_consolidate_reasons(
    amenity_reasons: dict[str, dict[str, list[str]]],
    client: OpenAI,
) -> dict[str, dict[str, list[str]]]:
    """
    For a batch of amenities, consolidates raw positive and negative reasons
    collected across multiple reviews into at most 3 clean, specific, distinct
    reasons per sentiment direction per amenity.

    Input:
        {
            "pool": {
                "positive": ["heated", "heated year round", "clean", "great"],
                "negative": ["crowded on weekends", "closed for maintenance"]
            },
            ...
        }

    Output:
        {
            "pool": {
                "positive": ["heated year-round", "clean and well-maintained"],
                "negative": ["crowded on weekends"]
            },
            ...
        }

    Rules applied by the model:
        - Remove vague sentiment words ("great", "bad", "nice", "terrible")
        - Merge near-duplicates into the most specific version
        - Favor reasons that appear frequently across reviews
        - Return at most 3 per direction; omit direction key if no valid reasons remain
    """
    if not amenity_reasons:
        return {}

    input_block = json.dumps(amenity_reasons, indent=2)

    prompt = f"""You are consolidating guest review reasons for specific hotel amenities.

Below is a JSON object where each key is an amenity. Each amenity has a "positive" list
(reasons guests gave for liking it) and/or a "negative" list (reasons for disliking it).
The lists may contain duplicates, near-duplicates, and vague entries collected across
many reviews.

INPUT:
{input_block}

For each amenity and each sentiment direction, produce a clean consolidated list by:

  1. REMOVE vague entries that add no information:
       e.g. "great", "nice", "bad", "terrible", "good", "not good", "amazing", "disappointing"

  2. MERGE near-duplicates into the single most specific version:
       e.g. ["heated", "heated pool", "pool was heated"] → ["heated"]
       e.g. ["slow wifi", "wifi was slow", "internet slow"] → ["slow wifi"]

  3. FAVOR entries that appeared frequently (treat repetition as a signal of importance)

  4. OUTPUT at most 3 reasons per direction — the most specific and most representative ones.
     If fewer than 3 valid reasons exist after cleaning, output however many remain.
     If no valid reasons remain for a direction, omit that key entirely.

Respond with ONLY a JSON object in the same shape as the input, but with cleaned lists.
No explanation, no markdown:
{{
  "amenity": {{
    "positive": ["reason", ...],
    "negative": ["reason", ...]
  }},
  ...
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        result = json.loads(_strip_fences(response.choices[0].message.content))

        # Validate shape — ensure output only contains amenities we sent in
        consolidated = {}
        for amenity in amenity_reasons:
            entry = result.get(amenity, {})
            cleaned = {}
            for direction in ("positive", "negative"):
                reasons = entry.get(direction, [])
                if isinstance(reasons, list):
                    valid = [r.strip() for r in reasons if isinstance(r, str) and r.strip()][:3]
                    if valid:
                        cleaned[direction] = valid
            if cleaned:
                consolidated[amenity] = cleaned
        return consolidated

    except Exception as e:
        print(f"  [LLM error] prompt_consolidate_reasons: {e}", file=sys.stderr)
        return {}
