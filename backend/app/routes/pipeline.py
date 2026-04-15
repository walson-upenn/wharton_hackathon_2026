import json
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from ..openai_caller import get_openai_client
from ..pipeline_data import (
    ROOT_DIR,
    build_review_session,
    criticality_tier,
    load_pipeline_data,
    property_summary,
)


pipeline_bp = Blueprint(
    "pipeline",
    __name__,
    template_folder=str(ROOT_DIR / "preprocessing" / "templates"),
)


def _json_error(message: str, status: int):
    return jsonify({"error": message}), status


@pipeline_bp.route("/api/properties", methods=["GET"])
def get_properties():
    data = load_pipeline_data()
    scored_properties = set(data["ask_scores"].keys())
    properties = []

    for property_id in scored_properties:
        summary = property_summary(property_id)
        properties.append({
            "property_id": property_id,
            "name": summary["name"],
            "city": summary["city"],
            "country": summary["country"],
            "location": summary["location"],
        })

    properties.sort(key=lambda item: (item["city"], item["country"], item["property_id"]))
    return jsonify(properties)


@pipeline_bp.route("/api/review-session", methods=["GET"])
@pipeline_bp.route("/api/review-session/<property_id>", methods=["GET"])
def get_review_session(property_id=None):
    session = build_review_session(property_id)
    if not session:
        return _json_error("No precomputed ask-score data is available.", 404)
    return jsonify(session)


@pipeline_bp.route("/api/demo/properties", methods=["GET"])
def demo_properties():
    return get_properties()


@pipeline_bp.route("/api/demo/gap-data/<property_id>", methods=["GET"])
def demo_gap_data(property_id):
    data = load_pipeline_data()
    ask_data = data["ask_scores"].get(property_id, [])
    review_count = len(data["review_profiles"].get(property_id, []))

    if not ask_data:
        return _json_error("No score data for this property.", 404)

    amenities = []
    for item in ask_data:
        stats = item.get("stats", {})
        mention_count = stats.get("num_mentions", 0)
        amenities.append({
            "amenity": item.get("amenity"),
            "importance": item.get("criticality", 0),
            "tier": criticality_tier(item.get("criticality", 0)),
            "ask_score": item.get("score", 0),
            "components": item.get("components", {}),
            "mention_rate": round(mention_count / review_count, 3) if review_count else 0,
            "avg_detail": stats.get("avg_detail") or 0,
            "avg_sentiment": stats.get("mean_sentiment"),
            "coverage": stats.get("coverage", 0),
        })

    amenities.sort(key=lambda item: -item["ask_score"])
    return jsonify({
        "property_id": property_id,
        "review_count": review_count,
        "amenities": amenities,
    })


@pipeline_bp.route("/api/demo/property-detail/<property_id>", methods=["GET"])
def demo_property_detail(property_id):
    data = load_pipeline_data()
    reviews = data["review_profiles"].get(property_id, [])
    ask_data = data["ask_scores"].get(property_id, [])

    if not reviews and not ask_data:
        return _json_error("No precomputed data for this property.", 404)

    ask_lookup = {item.get("amenity"): item for item in ask_data}
    review_count = len(reviews)
    buckets = [-1.0, -0.5, 0.0, 0.5, 1.0]
    sentiment_distributions = {}
    mention_counts = {}

    for review in reviews:
        for amenity, amenity_data in review.get("amenities", {}).items():
            sentiment_distributions.setdefault(amenity, {bucket: 0 for bucket in buckets})
            mention_counts[amenity] = mention_counts.get(amenity, 0) + 1

            sentiment = amenity_data.get("sentiment")
            if sentiment is not None:
                bucket = max(-1.0, min(1.0, round(sentiment * 2) / 2))
                sentiment_distributions[amenity][bucket] += 1

    amenities = []
    for amenity in set(ask_lookup) | set(sentiment_distributions):
        item = ask_lookup.get(amenity)
        mention_count = mention_counts.get(amenity, 0)
        distribution = {
            str(bucket): count
            for bucket, count in sentiment_distributions.get(
                amenity,
                {bucket: 0 for bucket in buckets},
            ).items()
        }

        if item:
            stats = item.get("stats", {})
            context = item.get("context", {})
            criticality = item.get("criticality", 0)
            ask_score = item.get("score", 0)
            components = item.get("components", {})
            positive_reasons = context.get("positive_reasons", [])[:5]
            negative_reasons = context.get("negative_reasons", [])[:5]
            avg_detail = stats.get("avg_detail") or 0
            avg_sentiment = stats.get("mean_sentiment")
            mention_rate = round(stats.get("num_mentions", 0) / review_count, 3) if review_count else 0
        else:
            criticality = data["amenity_profiles"].get(property_id, {}).get(amenity, 0.5)
            ask_score = 0
            components = {}
            positive_reasons = []
            negative_reasons = []
            avg_detail = 0
            avg_sentiment = None
            mention_rate = round(mention_count / review_count, 3) if review_count else 0

        amenities.append({
            "amenity": amenity,
            "importance": criticality,
            "tier": criticality_tier(criticality),
            "ask_score": ask_score,
            "components": components,
            "mention_count": mention_count,
            "mention_rate": mention_rate,
            "avg_detail": round(avg_detail, 2),
            "avg_sentiment": round(avg_sentiment, 2) if avg_sentiment is not None else None,
            "sentiment_dist": distribution,
            "positive_reasons": positive_reasons,
            "negative_reasons": negative_reasons,
        })

    amenities.sort(key=lambda item: -item["ask_score"])

    recent_reviews = sorted(
        [review for review in reviews if review.get("amenities")],
        key=lambda review: review.get("date", ""),
        reverse=True,
    )[:8]

    top_ask = amenities[0]["amenity"] if amenities else None
    avg_score = round(sum(item["ask_score"] for item in amenities) / len(amenities), 3) if amenities else 0
    prop = property_summary(property_id)

    return jsonify({
        "property": {
            "id": property_id,
            "city": prop["city"],
            "country": prop["country"],
            "type": "",
            "stars": prop["starRating"],
            "description": prop["description"],
        },
        "stats": {
            "review_count": review_count,
            "amenity_count": len(amenities),
            "top_ask": top_ask,
            "avg_score": avg_score,
        },
        "amenities": amenities,
        "recent_reviews": recent_reviews,
    })


@pipeline_bp.route("/api/demo/review-sample/<property_id>", methods=["GET"])
def demo_review_sample(property_id):
    data = load_pipeline_data()
    reviews = data["review_profiles"].get(property_id, [])
    if not reviews:
        return _json_error("No review data for this property.", 404)

    review = max(
        reviews,
        key=lambda item: len(item.get("amenities", {})) * 2
        + sum(
            1
            for amenity in item.get("amenities", {}).values()
            if amenity.get("sentiment") not in (None, 0)
        ),
    )

    amenities = []
    for amenity, amenity_data in review.get("amenities", {}).items():
        amenities.append({
            "amenity": amenity,
            "sentiment": amenity_data.get("sentiment"),
            "detail": amenity_data.get("detail", 0),
            "reasons": amenity_data.get("reasons", []),
        })

    amenities.sort(key=lambda item: -abs(item.get("sentiment") or 0))
    return jsonify({
        "date": review.get("date", ""),
        "title": review.get("title", ""),
        "text": review.get("text", ""),
        "amenities": amenities,
    })


@pipeline_bp.route("/api/reviews/voice/extract", methods=["POST"])
def extract_voice_review():
    payload = request.get_json(silent=True) or {}
    transcript_messages = payload.get("transcriptMessages") or []
    target_amenities = payload.get("targetAmenities") or []
    property_id = payload.get("propertyId") or ""

    transcript = "\n".join(
        f"{message.get('source', 'unknown')}: {message.get('text', '')}"
        for message in transcript_messages
        if isinstance(message, dict) and message.get("text")
    ).strip()

    if not transcript:
        return _json_error("Missing transcript messages.", 400)

    amenity_names = [
        item.get("amenity")
        for item in target_amenities
        if isinstance(item, dict) and item.get("amenity")
    ]

    try:
        client = get_openai_client()
    except RuntimeError as exc:
        return _json_error(str(exc), 503)

    prompt = f"""Extract structured hotel amenity observations from this voice review transcript.

Property id: {property_id}
Target amenities: {json.dumps(amenity_names)}

Transcript:
{transcript}

Return only valid JSON with this shape:
{{
  "amenities": [
    {{
      "amenity": "amenity name",
      "used": true,
      "sentiment": "positive|negative|mixed|neutral|unknown",
      "detail_score": 0,
      "facts": ["short verifiable fact"],
      "reasons": ["short reason phrase"],
      "supporting_quote": "short quote from transcript",
      "confidence": 0.0
    }}
  ],
  "summary": "one sentence"
}}

Only include amenities from the target list. Use detail_score from 0 to 4."""

    try:
        response = client.responses.create(
            model="gpt-5.4-mini",
            instructions="You extract concise structured hotel review facts. Return JSON only.",
            input=prompt,
        )
        raw = response.output_text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        extraction = json.loads(raw.strip())
    except Exception as exc:
        return _json_error(f"Could not extract structured review data: {exc}", 502)

    runtime_dir = ROOT_DIR / "backend" / "runtime"
    runtime_dir.mkdir(exist_ok=True)
    record = {
        "propertyId": property_id,
        "conversationId": payload.get("conversationId", ""),
        "transcriptMessages": transcript_messages,
        "targetAmenities": target_amenities,
        "extraction": extraction,
    }
    with (runtime_dir / "review_submissions.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")

    return jsonify(extraction)


@pipeline_bp.route("/pipeline-demo", methods=["GET"])
def pipeline_demo_page():
    return render_template("pipeline_demo.html")


@pipeline_bp.route("/property", methods=["GET"])
@pipeline_bp.route("/property/<property_id>", methods=["GET"])
def property_detail_page(property_id=""):
    return render_template("property_detail.html", initial_property_id=property_id or "")
