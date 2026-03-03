"""Catalog routes -- browse Superset datasets the user can access."""

from __future__ import annotations

import base64
import json
import logging
import time

from flask import Blueprint, current_app, jsonify, session

logger = logging.getLogger(__name__)

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/superset/catalog")


def _is_token_expired(token: str, buffer_seconds: int = 60) -> bool:
    """Decode the JWT exp claim and check if it's expired (or about to)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return time.time() > claims.get("exp", 0) - buffer_seconds
    except Exception:
        return False


def _require_auth():
    token = session.get("superset_token")
    user = session.get("superset_user")
    if not token or not user:
        return None, None

    if _is_token_expired(token):
        refresh_tok = session.get("superset_refresh_token")
        if refresh_tok:
            try:
                bridge = current_app.extensions["superset_bridge"]
                result = bridge.refresh_token(refresh_tok)
                new_token = result.get("access_token")
                if new_token:
                    session["superset_token"] = new_token
                    token = new_token
                    logger.info("Superset access_token 已自动刷新")
            except Exception as e:
                logger.warning("Superset token 刷新失败: %s", e)
                return None, None
        else:
            logger.warning("Superset access_token 已过期且无 refresh_token")
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
