"""Catalog routes -- browse Superset datasets the user can access."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, session

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/superset/catalog")


def _require_auth():
    token = session.get("superset_token")
    user = session.get("superset_user")
    if not token or not user:
        return None, None
    return token, user


@catalog_bp.route("/datasets", methods=["GET"])
def list_datasets():
    """List datasets visible to the current user."""
    token, user = _require_auth()
    if not token:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    catalog = current_app.extensions["superset_catalog"]
    datasets = catalog.get_catalog_summary(token, user["id"])
    return jsonify({"status": "ok", "datasets": datasets, "count": len(datasets)})


@catalog_bp.route("/datasets/<int:dataset_id>", methods=["GET"])
def get_dataset_detail(dataset_id: int):
    """Full detail for a single dataset."""
    token, _ = _require_auth()
    if not token:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    catalog = current_app.extensions["superset_catalog"]
    detail = catalog.get_dataset_detail(token, dataset_id)
    return jsonify({"status": "ok", "dataset": detail})
