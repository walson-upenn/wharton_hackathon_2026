import json
import os

from .openai_caller import get_openai_client


_QUESTION_CACHE: dict[str, dict[str, dict]] = {}
_BANNED_USER_COPY_TERMS = (
    "review",
    "previous",
    "historical",
    "history",
    "score",
    "ranking",
    "ranked",
    "data",
    "pipeline",
    "model",
    "json",
)
_GENERIC_REASON_PHRASES = (
    "we want",
    "we'd like",
    "we would like",
    "we're curious",
    "we are curious",
    "we're interested",
    "we are interested",
    "tell us",
    "hear about",
    "know more",
    "your personal experience",
)


def _clean_text(value, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback

    return " ".join(value.split()).strip() or fallback


def _trim_question(value: str, fallback: str) -> str:
    question = _clean_text(value, fallback)
    words = question.split()
    if len(words) <= 24:
        return question

    trimmed = " ".join(words[:24]).rstrip(".,;:")
    return f"{trimmed}?"


def _has_banned_user_copy(value: str) -> bool:
    text = value.lower()
    return any(term in text for term in _BANNED_USER_COPY_TERMS)


def _safe_generated_text(value, fallback: str) -> str:
    text = _clean_text(value, fallback)
    if _has_banned_user_copy(text):
        return fallback
    return text


def _amenity_question(amenity: str, focus: str) -> str:
    amenity_key = amenity.lower()
    templates = {
        "wifi": f"When you tried the Wi-Fi, {focus}",
        "wi-fi": f"When you tried the Wi-Fi, {focus}",
        "free parking": f"When you parked, {focus}",
        "parking": f"When you parked, {focus}",
        "front desk": f"During check-in or checkout, {focus}",
        "restaurant": f"At the restaurant, {focus}",
        "breakfast": f"At breakfast, {focus}",
        "pool": f"At the pool, {focus}",
        "fitness center": f"At the fitness center, {focus}",
        "gym": f"At the gym, {focus}",
        "room service": f"When you ordered room service, {focus}",
        "airport shuttle": f"When you used the airport shuttle, {focus}",
        "area shuttle": f"When you used the shuttle, {focus}",
        "housekeeping": f"When housekeeping came up, {focus}",
        "accessibility": f"When getting around the property, {focus}",
    }
    return templates.get(amenity_key, f"When you used {amenity}, {focus}")


def _is_generic_reason(value: str, amenity: str) -> bool:
    text = value.lower()
    if amenity.lower() not in text:
        return True
    return any(phrase in text for phrase in _GENERIC_REASON_PHRASES)


def _fallback_question_text(target: dict) -> str:
    amenity = target.get("amenity") or "this amenity"
    components = target.get("components", {})
    stats = target.get("stats", {})
    has_negative_context = bool(target.get("negative_reasons"))

    if components.get("controversy_score", 0) >= 0.35:
        return _amenity_question(amenity, "what was your actual experience?")
    if components.get("decline_score", 0) >= 0.2:
        return _amenity_question(amenity, "did it feel current and well maintained?")
    if components.get("staleness_score", 0) >= 0.7:
        return _amenity_question(amenity, "did it match what the hotel seemed to promise?")
    if stats.get("num_mentions", 0) == 0:
        return _amenity_question(amenity, "what stood out in that moment?")
    if has_negative_context:
        return _amenity_question(amenity, "did any issue come up?")
    return _amenity_question(amenity, "what detail would help future guests?")


def _fallback_selection_reason(target: dict) -> str:
    amenity = target.get("amenity") or "this amenity"
    components = target.get("components", {})
    stats = target.get("stats", {})

    if components.get("controversy_score", 0) >= 0.35:
        return f"Guests get mixed signals about {amenity}, so one concrete example helps."
    if components.get("decline_score", 0) >= 0.2 or components.get("staleness_score", 0) >= 0.7:
        return f"Details about {amenity} may be out of date, so your recent experience helps."
    if stats.get("num_mentions", 0) == 0 or components.get("knowledge_gap_score", 0) >= 0.75:
        return f"Future guests need concrete details about {amenity}, not just whether it was good."
    if target.get("negative_reasons"):
        return f"There are practical concerns around {amenity}, so your recent example adds clarity."
    return f"A specific detail about {amenity} helps future guests set expectations."


def fallback_form_question(target: dict) -> dict:
    amenity = target.get("amenity") or "this amenity"

    return {
        "primaryQuestion": _fallback_question_text(target),
        "placeholder": "A quick concrete detail is enough",
        "selectionReason": _fallback_selection_reason(target),
    }


def _fallback_questions(targets: list[dict]) -> dict[str, dict]:
    return {
        target["amenity"]: fallback_form_question(target)
        for target in targets
        if target.get("amenity")
    }


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]

    parsed = json.loads(text.strip())
    if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
        return {item.get("amenity"): item for item in parsed["questions"]}
    if isinstance(parsed, list):
        return {item.get("amenity"): item for item in parsed}
    if isinstance(parsed, dict):
        return parsed

    return {}


def _validate_question(amenity: str, raw_question, fallback: dict) -> dict:
    if not isinstance(raw_question, dict):
        return fallback

    primary = _trim_question(raw_question.get("primaryQuestion"), fallback["primaryQuestion"])
    if _has_banned_user_copy(primary):
        primary = fallback["primaryQuestion"]

    selection_reason = _safe_generated_text(
        raw_question.get("selectionReason"),
        fallback["selectionReason"],
    )
    if _is_generic_reason(selection_reason, amenity):
        selection_reason = fallback["selectionReason"]

    return {
        "primaryQuestion": primary,
        "placeholder": _safe_generated_text(raw_question.get("placeholder"), fallback["placeholder"]),
        "selectionReason": selection_reason,
        "amenity": amenity,
    }


def _question_prompt(property_summary: dict, targets: list[dict]) -> str:
    compact_targets = [
        {
            "amenity": target.get("amenity"),
            "priority_order": target.get("priority_order"),
            "ask_reason": target.get("ask_reason"),
            "question_angles": target.get("question_angles", [])[:3],
            "positive_context": target.get("positive_reasons", [])[:3],
            "negative_context": target.get("negative_reasons", [])[:3],
            "components": target.get("components", {}),
            "stats": target.get("stats", {}),
        }
        for target in targets
        if target.get("amenity")
    ]

    return f"""Generate low-friction form follow-up questions for a hotel review product.

Property:
{json.dumps(property_summary, ensure_ascii=False)}

Target amenities, already sorted by priority:
{json.dumps(compact_targets, ensure_ascii=False)}

Goal:
Create one form question for each exact amenity. The traveler will first select which amenities they used; the UI will ask only the highest-priority one or two selected amenities.

Question style:
- Ask about a specific remembered moment from the stay, not the whole stay.
- Keep primaryQuestion under 22 words when possible.
- Use plain, conversational English.
- Ask for observable details such as timing, availability, cleanliness, crowding, reliability, fees, condition, or whether a known issue matched their stay.
- Stay neutral. Do not imply the answer should be positive or negative.
- Do not mention scores, rankings, historical review gaps, models, JSON, data pipelines, or the existence of previous reviews.
- Do not ask for ratings.
- Do not generate a separate recall caption or "think back" helper text.

Selection reason style:
- Make selectionReason specific to the amenity and the uncertainty in the context.
- Name the amenity directly.
- Explain the useful gap without mentioning reviews, scores, rankings, models, JSON, data, or pipelines.
- Avoid generic phrases like "we're curious", "we want to know", "we'd like to hear", or "your personal experience".
- Good examples:
  - "Guests get mixed signals about parking, so one arrival example helps."
  - "Wi-Fi reliability can vary by use case, so a concrete moment is useful."
  - "Breakfast details change quickly, so a recent example helps set expectations."

Return only valid JSON with this shape:
{{
  "questions": [
    {{
      "amenity": "exact amenity name",
      "primaryQuestion": "short question",
      "placeholder": "short answer hint",
      "selectionReason": "short user-facing reason for asking"
    }}
  ]
}}"""


def build_form_questions(property_id: str, property_summary: dict, targets: list[dict]) -> dict[str, dict]:
    if property_id in _QUESTION_CACHE:
        return _QUESTION_CACHE[property_id]

    fallbacks = _fallback_questions(targets)
    generated = {}

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=os.getenv("FORM_QUESTION_MODEL", "gpt-4o-mini"),
            instructions=(
                "You write concise hotel review follow-up questions. "
                "Return valid JSON only."
            ),
            input=_question_prompt(property_summary, targets),
        )
        generated = _parse_json_object(response.output_text)
    except Exception:
        generated = {}

    questions = {
        amenity: _validate_question(amenity, generated.get(amenity), fallback)
        for amenity, fallback in fallbacks.items()
    }
    _QUESTION_CACHE[property_id] = questions
    return questions
