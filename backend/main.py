import os
from flask import Flask, jsonify, request
from dotenv import load_dotenv

from openai_caller import init_openai, chat


load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

    init_openai(app)

    @app.route("/")
    def home():
        return "Hello, Flask!"

    @app.route("/ask", methods=["POST"])
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

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)