from flask import Blueprint

default_bp = Blueprint("main", __name__)

@default_bp.route("/")
def home():
    return "Hello, Flask!"