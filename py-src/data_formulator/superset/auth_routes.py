"""Authentication routes -- proxy login through Superset JWT.

These routes are only active when SUPERSET_URL is configured.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets

from flask import Blueprint, current_app, jsonify, request, session

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _bridge():
    return current_app.extensions["superset_bridge"]


def _user_from_jwt_fallback(access_token: str, username: str) -> dict:
    """Build minimal user info from JWT claims when /api/v1/me is unavailable."""
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return {"id": None, "username": username, "first_name": "", "last_name": ""}
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
        claims = json.loads(decoded)
        user_id = claims.get("sub")
        try:
            user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            user_id = None
        return {"id": user_id, "username": username, "first_name": "", "last_name": ""}
    except Exception:
        logger.debug("JWT fallback parse failed", exc_info=True)
        return {"id": None, "username": username, "first_name": "", "last_name": ""}


@auth_bp.route("/login", methods=["POST"])
def login():
    """Proxy login: frontend -> DF backend -> Superset JWT."""
    if not current_app.config.get("SUPERSET_ENABLED"):
        return jsonify({"status": "error", "message": "Superset is not configured"}), 501

    data = request.get_json(force=True)
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"status": "error", "message": "Missing credentials"}), 400

    try:
        result = _bridge().login(username, password)
        access_token = result["access_token"]
        refresh_token = result.get("refresh_token")

        try:
            user_info = _bridge().get_user_info(access_token)
        except Exception as exc:
            logger.warning("Superset /api/v1/me unavailable, using JWT fallback: %s", exc)
            user_info = _user_from_jwt_fallback(access_token, username)

        session["superset_token"] = access_token
        session["superset_refresh_token"] = refresh_token
        session["superset_user"] = user_info
        session.permanent = True

        user_id = user_info.get("id")
        if user_id is not None:
            session["session_id"] = f"superset_user_{user_id}"
        elif "session_id" not in session:
            session["session_id"] = f"superset_anon_{secrets.token_hex(8)}"
        session.permanent = True

        return jsonify({
            "status": "ok",
            "user": {
                "id": user_info.get("id"),
                "username": user_info.get("username", ""),
                "first_name": user_info.get("first_name", ""),
                "last_name": user_info.get("last_name", ""),
            },
            "session_id": session["session_id"],
        })
    except Exception as exc:
        logger.warning("Login failed for %s: %s", username, exc)
        return jsonify({"status": "error", "message": str(exc)}), 401


@auth_bp.route("/me", methods=["GET"])
def me():
    """Return the current authenticated user (from session)."""
    user = session.get("superset_user")
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    return jsonify({"status": "ok", "user": user})


@auth_bp.route("/sso/save-tokens", methods=["POST"])
def sso_save_tokens():
    """Receive Superset JWT tokens obtained via the Popup SSO flow and persist them in the Flask session."""
    if not current_app.config.get("SUPERSET_ENABLED"):
        return jsonify({"status": "error", "message": "Superset is not configured"}), 501

    data = request.get_json(force=True)
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    user_from_popup = data.get("user", {})

    if not access_token:
        return jsonify({"status": "error", "message": "Missing access_token"}), 400

    try:
        user_info = _bridge().get_user_info(access_token)
    except Exception:
        user_info = user_from_popup

    if not user_info or not user_info.get("id"):
        user_info = _user_from_jwt_fallback(access_token, user_from_popup.get("username", ""))

    session["superset_token"] = access_token
    session["superset_refresh_token"] = refresh_token
    session["superset_user"] = user_info
    session.permanent = True

    user_id = user_info.get("id")
    if user_id is not None:
        session["session_id"] = f"superset_user_{user_id}"
    elif "session_id" not in session:
        session["session_id"] = f"superset_anon_{secrets.token_hex(8)}"
    session.permanent = True

    return jsonify({
        "status": "ok",
        "user": {
            "id": user_info.get("id"),
            "username": user_info.get("username", ""),
            "first_name": user_info.get("first_name", ""),
            "last_name": user_info.get("last_name", ""),
        },
        "session_id": session["session_id"],
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear session data."""
    session.clear()
    return jsonify({"status": "ok"})
