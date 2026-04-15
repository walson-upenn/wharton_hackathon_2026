import os

import httpx
from flask import Blueprint, jsonify


elevenlabs_bp = Blueprint("elevenlabs", __name__)


@elevenlabs_bp.route("/elevenlabs/conversation-token", methods=["GET"])
def get_conversation_token():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    agent_id = os.getenv("ELEVENLABS_AGENT_ID")

    if not api_key or not agent_id:
        return jsonify({
            "error": "ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID must be set."
        }), 500

    try:
        response = httpx.get(
            "https://api.elevenlabs.io/v1/convai/conversation/token",
            params={"agent_id": agent_id},
            headers={"xi-api-key": api_key},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return jsonify({
            "error": "ElevenLabs rejected the conversation token request.",
            "status_code": exc.response.status_code,
        }), 502
    except httpx.HTTPError:
        return jsonify({
            "error": "Could not reach ElevenLabs for a conversation token."
        }), 502

    data = response.json()
    token = data.get("token")

    if not token:
        return jsonify({
            "error": "ElevenLabs response did not include a conversation token."
        }), 502

    return jsonify({"token": token})


@elevenlabs_bp.route("/elevenlabs/signed-url", methods=["GET"])
def get_signed_url():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    agent_id = os.getenv("ELEVENLABS_AGENT_ID")

    if not api_key or not agent_id:
        return jsonify({
            "error": "ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID must be set."
        }), 500

    try:
        response = httpx.get(
            "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url",
            params={
                "agent_id": agent_id,
                "include_conversation_id": "true",
            },
            headers={"xi-api-key": api_key},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return jsonify({
            "error": "ElevenLabs rejected the signed URL request.",
            "status_code": exc.response.status_code,
        }), 502
    except httpx.HTTPError:
        return jsonify({
            "error": "Could not reach ElevenLabs for a signed URL."
        }), 502

    data = response.json()
    signed_url = data.get("signed_url")

    if not signed_url:
        return jsonify({
            "error": "ElevenLabs response did not include a signed URL."
        }), 502

    return jsonify({"signedUrl": signed_url})
