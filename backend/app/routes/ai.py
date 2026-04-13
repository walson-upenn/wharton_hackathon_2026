from flask import Blueprint, jsonify, request
from ..openai_caller import chat

ai_bp = Blueprint("ai", __name__)

@ai_bp.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Missing 'message' in JSON body."}), 400

    try:
        reply = chat(message)
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500