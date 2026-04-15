import csv
import json
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SOURCES_DIR = ROOT_DIR / "sources"
SCORING_DIR = ROOT_DIR / "scoring"
FINAL_PREPROCESSING_DIR = ROOT_DIR / "final-preprocessing"


def _load_json(path: Path, default):
    if not path.exists():
        return default

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@lru_cache(maxsize=1)
def load_pipeline_data() -> dict:
    descriptions = _load_csv(SOURCES_DIR / "Description_PROC.csv")
    reviews = _load_csv(SOURCES_DIR / "Reviews_PROC.csv")

    return {
        "descriptions": descriptions,
        "reviews": reviews,
        "properties": {row.get("eg_property_id"): row for row in descriptions},
        "ask_scores": _load_json(SCORING_DIR / "ask_scores.json", {}),
        "review_profiles": _load_json(FINAL_PREPROCESSING_DIR / "review_profiles.json", {}),
        "amenity_profiles": _load_json(FINAL_PREPROCESSING_DIR / "amenity_profiles.json", {}),
        "aggregated_reasons": _load_json(FINAL_PREPROCESSING_DIR / "aggregated_reasons.json", {}),
    }


def criticality_tier(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "important"
    if score >= 0.25:
        return "moderate"
    return "minor"


def property_summary(property_id: str, row: dict | None = None) -> dict:
    data = load_pipeline_data()
    prop = row or data["properties"].get(property_id, {})
    city = (prop.get("city") or "").strip()
    province = (prop.get("province") or "").strip()
    country = (prop.get("country") or "").strip()
    location = ", ".join(part for part in [city, province or country] if part)

    return {
        "id": property_id,
        "name": prop.get("property_name") or prop.get("city") or f"Hotel {property_id[:8]}",
        "location": location or country or "Selected property",
        "city": city,
        "province": province,
        "country": country,
        "starRating": prop.get("star_rating") or "",
        "description": prop.get("property_description") or "",
    }


def ask_reason(item: dict) -> str:
    components = item.get("components", {})
    stats = item.get("stats", {})
    context = item.get("context", {})

    reasons = []
    if stats.get("num_mentions", 0) == 0:
        reasons.append("no recent review gives usable detail")
    elif components.get("knowledge_gap_score", 0) >= 0.75:
        reasons.append("existing reviews mention it without enough concrete detail")

    if components.get("controversy_score", 0) >= 0.35:
        reasons.append("traveler reviews disagree")
    if components.get("decline_score", 0) >= 0.2:
        reasons.append("recent sentiment appears worse than older reviews")
    if components.get("staleness_score", 0) >= 0.7:
        reasons.append("the latest useful mention is stale")

    if not reasons:
        if context.get("negative_reasons"):
            reasons.append("recent reviews raise unresolved concerns")
        else:
            reasons.append("it is important for this property")

    return "; ".join(reasons)


def question_angles(item: dict) -> list[str]:
    components = item.get("components", {})
    context = item.get("context", {})
    stats = item.get("stats", {})
    angles = []

    if stats.get("num_mentions", 0) == 0:
        angles.append("ask whether they used it and what specifically stood out")
    elif components.get("knowledge_gap_score", 0) >= 0.75:
        angles.append("ask for concrete details because existing reviews are thin")

    if components.get("controversy_score", 0) >= 0.35:
        angles.append("ask what their actual experience was because reviews disagree")

    if components.get("decline_score", 0) >= 0.2:
        angles.append("ask whether it felt worse or changed recently")

    if components.get("staleness_score", 0) >= 0.7:
        angles.append("ask whether the current experience matches older reviews")

    if context.get("negative_reasons"):
        angles.append("ask if the known concern matched their stay")

    if not angles:
        angles.append("ask for one useful, specific detail")

    return angles[:3]


def build_target_amenities(property_id: str, limit: int = 5) -> list[dict]:
    data = load_pipeline_data()
    rows = data["ask_scores"].get(property_id, [])[:limit]

    targets = []
    for index, item in enumerate(rows):
        context = item.get("context", {})
        targets.append({
            "amenity": item.get("amenity"),
            "priority_order": index + 1,
            "score": item.get("score", 0),
            "criticality": item.get("criticality", 0),
            "components": item.get("components", {}),
            "stats": item.get("stats", {}),
            "positive_reasons": context.get("positive_reasons", []),
            "negative_reasons": context.get("negative_reasons", []),
            "ask_reason": ask_reason(item),
            "question_angles": question_angles(item),
        })

    return targets


def build_agent_context(property_id: str, targets: list[dict]) -> dict:
    prop = property_summary(property_id)
    compact_targets = [
        {
            "amenity": target["amenity"],
            "priority_order": target["priority_order"],
            "ask_reason": target["ask_reason"],
            "positive_context": target["positive_reasons"][:2],
            "negative_context": target["negative_reasons"][:2],
            "question_angles": target["question_angles"],
        }
        for target in targets
    ]
    target_names = [target["amenity"] for target in targets if target.get("amenity")]
    target_brief = "\n".join(
        f"{target['priority_order']}. {target['amenity']}: {target['ask_reason']}. "
        f"Question angle: {target['question_angles'][0]}"
        for target in targets
    )

    strategy = (
        "Ask which target amenities the guest actually used. "
        "Then ask at most two short follow-up questions about used amenities only. "
        "Prefer specific, observable details about quality, condition, availability, "
        "fees, crowding, reliability, or recent changes."
    )

    return {
        "property_name": prop["name"],
        "property_location": prop["location"],
        "target_amenities_json": json.dumps(compact_targets, ensure_ascii=False),
        "target_amenities_brief": target_brief,
        "target_amenity_names": ", ".join(target_names),
        "question_strategy": strategy,
        "first_message": (
            f"Thanks for reviewing {prop['name']}. I'll keep this under a minute "
            f"and only ask what helps future travelers. Did you use any of these "
            f"during your stay: {', '.join(target_names)}?"
        ),
    }


def build_review_session(property_id: str | None = None) -> dict | None:
    data = load_pipeline_data()
    ask_scores = data["ask_scores"]
    selected_id = property_id or next(iter(ask_scores), None)

    if not selected_id or selected_id not in ask_scores:
        return None

    targets = build_target_amenities(selected_id)
    prop = property_summary(selected_id)
    prop["stayRange"] = "Recent stay"

    return {
        "reviewId": f"review_{selected_id[:8]}",
        "propertyId": selected_id,
        "property": prop,
        "targetAmenities": targets,
        "stayUsageQuestion": {
            "id": "stay_usage",
            "label": "Which of these did you use during your stay?",
            "options": [target["amenity"] for target in targets],
        },
        "questions": [
            {
                "id": f"q_{index + 1}",
                "type": "text",
                "amenity": target["amenity"],
                "label": f"What should future travelers know about the {target['amenity']}?",
                "askReason": target["ask_reason"],
                "placeholder": "Share one or two specific details",
                "required": False,
            }
            for index, target in enumerate(targets[:2])
        ],
        "elevenLabsContext": build_agent_context(selected_id, targets),
    }
