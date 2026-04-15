import json
from pathlib import Path

from app import create_app
from app.pipeline_data import build_all_review_sessions


BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
OUTPUT_PATH = ROOT_DIR / "frontend" / "public" / "data" / "review-sessions.json"


def build_properties(sessions: list[dict]) -> list[dict]:
    properties = []

    for session in sessions:
        prop = session.get("property", {})
        property_id = session.get("propertyId", "")
        properties.append({
            "property_id": property_id,
            "name": prop.get("name", ""),
            "city": prop.get("city", ""),
            "country": prop.get("country", ""),
            "location": prop.get("location", ""),
        })

    properties.sort(key=lambda item: (item["city"], item["country"], item["property_id"]))
    return properties


def main() -> None:
    app = create_app()

    with app.app_context():
        sessions = build_all_review_sessions()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "properties": build_properties(sessions),
        "sessions": sessions,
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"Wrote {len(sessions)} review sessions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
