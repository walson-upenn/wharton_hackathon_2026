import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from .openai_caller import init_openai
from .routes.default import default_bp
from .routes.ai import ai_bp
from .routes.elevenlabs import elevenlabs_bp
from .routes.pipeline import pipeline_bp

load_dotenv()  # loads variables from .env into environment

def create_app():
    app = Flask(__name__)

    CORS(
        app,
        resources={
            r"/api/.*": {
                "origins": [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://localhost:5174",
                    "http://127.0.0.1:5174",
                    "https://wharton-hackathon-2026.vercel.app",
                ]
            }
        }
    )

    app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

    init_openai(app)

    app.register_blueprint(default_bp)
    app.register_blueprint(ai_bp, url_prefix="/api")
    app.register_blueprint(elevenlabs_bp, url_prefix="/api")
    app.register_blueprint(pipeline_bp)

    return app
