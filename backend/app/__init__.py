import os
from flask import Flask
from dotenv import load_dotenv
from .openai_caller import init_openai
from .routes.app import main_bp
from .routes.ai import ai_bp

load_dotenv()  # loads variables from .env into environment

def create_app():
    app = Flask(__name__)
    app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

    init_openai(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(ai_bp, url_prefix="/api")

    return app