import json
import math
import os

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

import database as db

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _is_nonempty_string(value):
    return isinstance(value, str) and value.strip() != ""


def _is_finite_number(value):
    # bool is a subclass of int, so exclude it explicitly: True is not a value.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


@app.errorhandler(Exception)
def handle_unexpected(e):
    """
    Backstop so the API never leaks an HTML stack trace: any unhandled
    exception becomes a clean JSON 500. Flask's own HTTP errors (404, 405,
    etc.) are passed through unchanged.
    """
    if isinstance(e, HTTPException):
        return e
    app.logger.exception("Unhandled error")
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

@app.cli.command("init-db")
def init_db_command():
    """Create database tables."""
    db.init_db()
    print("Database initialized.")


@app.cli.command("seed-db")
def seed_db_command():
    """Seed the database with sample calibration data from seed_data.txt."""
    seed_path = os.path.join(os.path.dirname(__file__), "seed_data.txt")
    with open(seed_path) as f:
        records = json.load(f)
    db.seed_db(records)
    print(f"Seeded {len(records)} calibrations.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """API overview."""
    return jsonify({
        "service": "Calibration API",
        "endpoints": [
            {"method": "POST",   "path": "/calibrations",                          "description": "Create a calibration"},
            {"method": "GET",    "path": "/calibrations",                          "description": "List/filter calibrations (params: user, type, tag, start, end)"},
            {"method": "POST",   "path": "/calibrations/{id}/tags",                "description": "Add a calibration to a tag"},
            {"method": "DELETE", "path": "/calibrations/{id}/tags/{tag_name}",     "description": "Remove a calibration from a tag"},
            {"method": "GET",    "path": "/calibrations/{id}/tags",                "description": "List tags for a calibration"},
        ],
    }), 200


@app.route("/calibrations", methods=["POST"])
def create_calibration():
    """Create a new calibration."""
    body = request.get_json(silent=True) or {}
    missing = [f for f in ("calibration_type", "value", "username") if f not in body]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    if not _is_nonempty_string(body["calibration_type"]):
        return jsonify({"error": "'calibration_type' must be a non-empty string"}), 400
    if not _is_nonempty_string(body["username"]):
        return jsonify({"error": "'username' must be a non-empty string"}), 400
    if not _is_finite_number(body["value"]):
        return jsonify({"error": "'value' must be a finite number"}), 400

    result = db.create_calibration(
        calibration_type=body["calibration_type"],
        value=body["value"],
        username=body["username"],
    )
    return jsonify(result), 201


@app.route("/calibrations", methods=["GET"])
def list_calibrations():
    """
    Retrieve calibrations with optional filters.

    Query parameters:
      user   – filter by username
      type   – filter by calibration_type
      tag    – filter by currently-active tag
      start  – ISO 8601 timestamp; return calibrations at or after this time
      end    – ISO 8601 timestamp; return calibrations at or before this time

    Timestamps may be given in any timezone (or none, in which case UTC is
    assumed); they are normalized to UTC before filtering.
    """
    try:
        start = request.args.get("start")
        start = db.parse_timestamp(start) if start else None
        end = request.args.get("end")
        end = db.parse_timestamp(end) if end else None
    except ValueError:
        return jsonify({
            "error": "'start' and 'end' must be ISO 8601 timestamps "
                     "(e.g. 2026-01-01 or 2026-01-01T09:30:00+00:00)"
        }), 400

    tag = request.args.get("tag")
    results = db.get_calibrations(
        user=request.args.get("user"),
        cal_type=request.args.get("type"),
        tag=tag.lower() if tag else None,
        start=start,
        end=end,
    )
    return jsonify(results), 200


@app.route("/calibrations/<int:cal_id>/tags", methods=["POST"])
def add_to_tag(cal_id):
    """Add a calibration to a tag (tag is created if it does not exist)."""
    body = request.get_json(silent=True) or {}
    tag = body.get("tag")
    if not _is_nonempty_string(tag):
        return jsonify({"error": "'tag' is required and must be a non-empty string"}), 400
    tag_name = tag.strip().lower()

    result, error = db.add_to_tag(cal_id, tag_name)
    if error == "calibration_not_found":
        return jsonify({"error": f"Calibration {cal_id} not found"}), 404
    if error == "already_in_tag":
        return jsonify({"error": f"Calibration {cal_id} is already in tag '{tag_name}'"}), 409

    return jsonify(result), 201


@app.route("/calibrations/<int:cal_id>/tags/<path:tag_name>", methods=["DELETE"])
def remove_from_tag(cal_id, tag_name):
    """Remove a calibration from a tag."""
    # Match the normalization applied when the tag was added.
    success, error = db.remove_from_tag(cal_id, tag_name.strip().lower())
    if error == "not_found":
        return jsonify({"error": f"Calibration {cal_id} is not currently in tag '{tag_name}'"}), 404

    return "", 204


@app.route("/calibrations/<int:cal_id>/tags", methods=["GET"])
def get_tags(cal_id):
    """
    Return all tag associations for a calibration (active and historical).

    Each entry includes 'time_removed': null means the association is still active.
    """
    tags = db.get_tags_for_calibration(cal_id)
    if tags is None:
        return jsonify({"error": f"Calibration {cal_id} not found"}), 404

    return jsonify(tags), 200


if __name__ == "__main__":
    app.run(debug=True)
