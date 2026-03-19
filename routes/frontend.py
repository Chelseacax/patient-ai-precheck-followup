from flask import Blueprint, send_from_directory

bp = Blueprint("frontend", __name__)


@bp.get("/")
def index():
    return send_from_directory("static", "index.html")


@bp.get("/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)
