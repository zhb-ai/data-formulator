"""Catalog routes -- browse Superset datasets the user can access."""

from __future__ import annotations

import base64
import json
import logging
import time

from flask import Blueprint, current_app, jsonify, session
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/superset/catalog")


def _is_token_expired(token: str, buffer_seconds: int = 60) -> bool:
    """Decode the JWT exp claim and check if it's expired (or about to).
    Returns True on parse failure (conservative: prefer refresh over stale use)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return time.time() > claims.get("exp", 0) - buffer_seconds
    except Exception:
        return True


def _try_refresh() -> str | None:
    """Attempt to refresh the Superset access_token.  Returns the new token
    on success, or None on failure."""
    refresh_tok = session.get("superset_refresh_token")
    if not refresh_tok:
        logger.warning("Superset access_token 已过期且无 refresh_token")
        return None
    try:
        bridge = current_app.extensions["superset_bridge"]
        result = bridge.refresh_token(refresh_tok)
        new_token = result.get("access_token")
        if new_token:
            session["superset_token"] = new_token
            logger.info("Superset access_token 已自动刷新")
            return new_token
    except Exception as e:
        logger.warning("Superset token 刷新失败: %s", e)
    return None


def _require_auth():
    token = session.get("superset_token")
    user = session.get("superset_user")
    if not token or not user:
        return None, None

    if _is_token_expired(token):
        token = _try_refresh()
        if not token:
            return None, None

    return token, user


@catalog_bp.route("/datasets", methods=["GET"])
def list_datasets():
    """List datasets visible to the current user."""
    token, user = _require_auth()
    if not token:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    catalog = current_app.extensions["superset_catalog"]
    try:
        datasets = catalog.get_catalog_summary(token, user["id"])
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            logger.info("Superset API 返回 401，尝试刷新 token 后重试")
            token = _try_refresh()
            if token:
                try:
                    datasets = catalog.get_catalog_summary(token, user["id"])
                except Exception as retry_err:
                    logger.warning("刷新后重试仍然失败: %s", retry_err)
                    return jsonify({"status": "error", "message": "Superset 认证失败，请重新登录"}), 401
            else:
                return jsonify({"status": "error", "message": "Superset 认证已过期，请重新登录"}), 401
        else:
            logger.warning("Superset API 调用失败: %s", e)
            return jsonify({"status": "error", "message": f"Superset 请求失败: {e}"}), 502
    except Exception as e:
        logger.warning("获取数据集列表失败: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "datasets": datasets, "count": len(datasets)})


@catalog_bp.route("/dashboards", methods=["GET"])
def list_dashboards():
    """List dashboards visible to the current user."""
    token, user = _require_auth()
    if not token:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    catalog = current_app.extensions["superset_catalog"]
    try:
        dashboards = catalog.get_dashboard_summary(token, user["id"])
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            logger.info("Superset API 返回 401，尝试刷新 token 后重试")
            token = _try_refresh()
            if token:
                try:
                    dashboards = catalog.get_dashboard_summary(token, user["id"])
                except Exception as retry_err:
                    logger.warning("刷新后重试仍然失败: %s", retry_err)
                    return jsonify({"status": "error", "message": "Superset 认证失败，请重新登录"}), 401
            else:
                return jsonify({"status": "error", "message": "Superset 认证已过期，请重新登录"}), 401
        else:
            logger.warning("Superset API 调用失败: %s", e)
            return jsonify({"status": "error", "message": f"Superset 请求失败: {e}"}), 502
    except Exception as e:
        logger.warning("获取仪表盘列表失败: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "dashboards": dashboards, "count": len(dashboards)})


@catalog_bp.route("/dashboards/<int:dashboard_id>/datasets", methods=["GET"])
def get_dashboard_datasets(dashboard_id: int):
    """Get datasets used by a specific dashboard."""
    token, user = _require_auth()
    if not token:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    catalog = current_app.extensions["superset_catalog"]
    try:
        datasets = catalog.get_dashboard_datasets(token, dashboard_id)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            token = _try_refresh()
            if token:
                try:
                    datasets = catalog.get_dashboard_datasets(token, dashboard_id)
                except Exception:
                    return jsonify({"status": "error", "message": "Superset 认证失败，请重新登录"}), 401
            else:
                return jsonify({"status": "error", "message": "Superset 认证已过期，请重新登录"}), 401
        else:
            return jsonify({"status": "error", "message": f"Superset 请求失败: {e}"}), 502
    except Exception as e:
        logger.warning("获取仪表盘数据集失败: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "datasets": datasets, "count": len(datasets)})


@catalog_bp.route("/datasets/<int:dataset_id>", methods=["GET"])
def get_dataset_detail(dataset_id: int):
    """Full detail for a single dataset."""
    token, _ = _require_auth()
    if not token:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    catalog = current_app.extensions["superset_catalog"]
    try:
        detail = catalog.get_dataset_detail(token, dataset_id)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            logger.info("Superset API 返回 401，尝试刷新 token 后重试")
            token = _try_refresh()
            if token:
                try:
                    detail = catalog.get_dataset_detail(token, dataset_id)
                except Exception as retry_err:
                    logger.warning("刷新后重试仍然失败: %s", retry_err)
                    return jsonify({"status": "error", "message": "Superset 认证失败，请重新登录"}), 401
            else:
                return jsonify({"status": "error", "message": "Superset 认证已过期，请重新登录"}), 401
        else:
            logger.warning("Superset API 调用失败: %s", e)
            return jsonify({"status": "error", "message": f"Superset 请求失败: {e}"}), 502
    except Exception as e:
        logger.warning("获取数据集详情失败: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "dataset": detail})
