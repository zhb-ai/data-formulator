# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import random
import sys
import os
import mimetypes
from functools import lru_cache
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/javascript', '.mjs')

import flask
from flask import Flask, request, send_from_directory, session
from flask import stream_with_context, Response

import webbrowser
import threading
import numpy as np
import datetime
import time

import logging

import json
from pathlib import Path

from dotenv import load_dotenv
import secrets
import base64
APP_ROOT = Path(Path(__file__).parent).absolute()

import os

# Load env files BEFORE importing any blueprint that initialises module-level
# singletons (e.g. model_registry).  If load_dotenv ran after the imports,
# those singletons would read an empty environment and find no models.
# PROJECT_ROOT = data-formulator/  (two levels up from py-src/data_formulator/)
_PROJECT_ROOT = Path(APP_ROOT, "..", "..").resolve()
load_dotenv(os.path.join(_PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(_PROJECT_ROOT, 'api-keys.env'))
load_dotenv(os.path.join(APP_ROOT, 'api-keys.env'))
load_dotenv(os.path.join(APP_ROOT, '.env'))

# blueprints
from data_formulator.tables_routes import tables_bp
from data_formulator.agent_routes import agent_bp
from data_formulator.demo_stream_routes import demo_stream_bp, limiter as demo_stream_limiter
from data_formulator.db_manager import db_manager
from data_formulator.example_datasets_config import EXAMPLE_DATASETS

import queue
from typing import Dict, Any

app = Flask(__name__, static_url_path='', static_folder=os.path.join(APP_ROOT, "dist"))


def _get_stable_secret_key() -> str:
    """Return a persistent Flask secret key.

    If FLASK_SECRET_KEY is already set (via .env or environment), use it
    directly.  Otherwise auto-generate one and append it to the project
    root .env so it survives server restarts — keeping anonymous user
    sessions (and their DuckDB databases) intact.
    """
    env_key = os.environ.get('FLASK_SECRET_KEY', '').strip()
    if env_key:
        return env_key

    new_key = secrets.token_hex(32)
    env_file = _PROJECT_ROOT / '.env'
    try:
        existing = env_file.read_text(encoding='utf-8') if env_file.exists() else ''
        sep = '' if existing.endswith('\n') or not existing else '\n'
        env_file.write_text(
            existing + f'{sep}\nFLASK_SECRET_KEY={new_key}\n',
            encoding='utf-8',
        )
    except OSError:
        pass
    os.environ['FLASK_SECRET_KEY'] = new_key
    return new_key


app.secret_key = _get_stable_secret_key()
app.json.sort_keys = False
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 365,  # 365 days
)

# Initialize rate limiter for demo stream routes that call external APIs
# The limiter is defined in demo_stream_routes.py to avoid circular imports
demo_stream_limiter.init_app(app)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.int64):
            return int(obj)
        if isinstance(obj, (bytes, bytearray)):
            return base64.b64encode(obj).decode('ascii')
        return super().default(obj)

app.json_encoder = CustomJSONEncoder

# Add this line to store args at app level
app.config['CLI_ARGS'] = {
    'exec_python_in_subprocess': os.environ.get('EXEC_PYTHON_IN_SUBPROCESS', 'false').lower() == 'true',
    'disable_display_keys': os.environ.get('DISABLE_DISPLAY_KEYS', 'false').lower() == 'true',
    'disable_database': os.environ.get('DISABLE_DATABASE', 'false').lower() == 'true',
    'disable_file_upload': os.environ.get('DISABLE_FILE_UPLOAD', 'false').lower() == 'true',
    'project_front_page': os.environ.get('PROJECT_FRONT_PAGE', 'false').lower() == 'true'
}
app.config['SUPERSET_URL'] = os.environ.get('SUPERSET_URL', '')
app.config['SUPERSET_ENABLED'] = bool(app.config['SUPERSET_URL'])

# register blueprints
# Only register tables blueprint if database is not disabled
if not app.config['CLI_ARGS']['disable_database']:
    app.register_blueprint(tables_bp)
app.register_blueprint(agent_bp)
app.register_blueprint(demo_stream_bp)

# Superset integration blueprints (only when SUPERSET_URL is configured)
if app.config['SUPERSET_ENABLED']:
    from data_formulator.superset.auth_bridge import SupersetAuthBridge
    from data_formulator.superset.auth_routes import auth_bp
    from data_formulator.superset.superset_client import SupersetClient
    from data_formulator.superset.catalog import SupersetCatalog
    from data_formulator.superset.catalog_routes import catalog_bp
    from data_formulator.superset.data_routes import superset_data_bp

    bridge = SupersetAuthBridge(app.config['SUPERSET_URL'])
    app.extensions["superset_bridge"] = bridge

    superset_client = SupersetClient(app.config['SUPERSET_URL'])
    app.extensions["superset_client"] = superset_client

    catalog_ttl = int(os.environ.get('CATALOG_CACHE_TTL', '300'))
    catalog = SupersetCatalog(superset_client, cache_ttl=catalog_ttl)
    app.extensions["superset_catalog"] = catalog

    app.register_blueprint(auth_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(superset_data_bp)
else:
    from data_formulator.superset.auth_routes import auth_bp
    app.register_blueprint(auth_bp)

# Get logger for this module (logging config moved to run_app function)
logger = logging.getLogger(__name__)

def configure_logging():
    """Configure logging for the Flask application."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    app_log_level = getattr(logging, log_level_str, logging.INFO)

    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    logging.getLogger('data_formulator').setLevel(app_log_level)

    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('litellm').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)

    # Configure Flask app logger to use the same settings
    app.logger.handlers = []
    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)

    logging.getLogger('data_formulator').info(f"日志级别: {log_level_str}")


OPEN_ENDPOINTS = frozenset([
    '/api/get-session-id',
    '/api/app-config',
    '/api/example-datasets',
    '/api/agent/check-available-models',
    '/api/hello',
    '/api/hello-stream',
    '/api/auth/login',
    '/api/auth/me',
    '/api/auth/logout',
    '/api/auth/sso/save-tokens',
])

@app.before_request
def enforce_session():
    """Reject requests to protected endpoints when no valid session exists."""
    path = request.path
    if path.startswith('/api/') and path not in OPEN_ENDPOINTS:
        if 'session_id' not in session:
            return flask.jsonify({
                "status": "error",
                "message": "No session ID found. Please visit the app first."
            }), 401


@app.route('/api/example-datasets')
def get_sample_datasets():
    return flask.jsonify(EXAMPLE_DATASETS)


@app.route("/", defaults={"path": ""})
def index_alt(path):
    logger.info(app.static_folder)
    return send_from_directory(app.static_folder, "index.html")

@app.errorhandler(404)
def page_not_found(e):
    # your processing here
    logger.info(app.static_folder)
    return send_from_directory(app.static_folder, "index.html") #'Hello 404!' #send_from_directory(app.static_folder, "index.html")

###### test functions ######

@app.route('/api/hello')
def hello():
    values = [
            {"a": "A", "b": 28}, {"a": "B", "b": 55}, {"a": "C", "b": 43},
            {"a": "D", "b": 91}, {"a": "E", "b": 81}, {"a": "F", "b": 53},
            {"a": "G", "b": 19}, {"a": "H", "b": 87}, {"a": "I", "b": 52}
        ]
    spec =  {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "A simple bar chart with embedded data.",
        "data": { "values": values },
        "mark": "bar",
        "encoding": {
            "x": {"field": "a", "type": "nominal", "axis": {"labelAngle": 0}},
            "y": {"field": "b", "type": "quantitative"}
        }
    }
    return json.dumps(spec)

@app.route('/api/hello-stream')
def streamed_response():
    def generate():
        values = [
            {"a": "A", "b": 28}, {"a": "B", "b": 55}, {"a": "C", "b": 43},
            {"a": "D", "b": 91}, {"a": "E", "b": 81}, {"a": "F", "b": 53},
            {"a": "G", "b": 19}, {"a": "H", "b": 87}, {"a": "I", "b": 52}
        ]
        spec =  {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": "A simple bar chart with embedded data.",
            "data": { "values": [] },
            "mark": "bar",
            "encoding": {
                "x": {"field": "a", "type": "nominal", "axis": {"labelAngle": 0}},
                "y": {"field": "b", "type": "quantitative"}
            }
        }
        for i in range(3):
            time.sleep(3)
            spec["data"]["values"] = values[i:]
            yield json.dumps(spec)
    return Response(stream_with_context(generate()))

@app.route('/api/get-session-id', methods=['GET', 'POST'])
def get_session_id():
    """Return the server-controlled session ID.

    The session ID is always generated server-side and stored in a
    HttpOnly cookie.  The client MUST NOT be able to choose or override
    its own session ID — doing so would allow one user to access another
    user's DuckDB database file.

    However, when a session cookie has expired but the client still holds
    a previous session_id in localStorage, the client may send it via
    ``recover_session_id`` in the JSON body.  The server will accept it
    **only if** the corresponding DuckDB file already exists on disk,
    preventing fabrication of arbitrary session IDs.
    """
    database_disabled = app.config['CLI_ARGS']['disable_database']

    if 'session_id' not in session:
        recovered = _try_recover_session(database_disabled)
        if not recovered:
            session['session_id'] = secrets.token_hex(16)
            logger.info(f"Created new session: {session['session_id']}")
        session.permanent = True

    return flask.jsonify({
        "status": "ok",
        "session_id": session['session_id']
    })


def _try_recover_session(database_disabled: bool) -> bool:
    """Try to restore a previous anonymous session from the client hint.

    Returns True if the session was successfully recovered.
    """
    if database_disabled:
        return False

    data = request.get_json(silent=True) or {}
    candidate = (data.get("recover_session_id") or "").strip()
    if not candidate:
        return False

    # Only allow hex-style anonymous session IDs (32 hex chars)
    if not all(c in "0123456789abcdef" for c in candidate) or len(candidate) != 32:
        logger.warning("Rejected session recovery: invalid format")
        return False

    db_dir = db_manager._local_db_dir or __import__("tempfile").gettempdir()
    db_path = os.path.join(db_dir, f"df_{candidate}.duckdb")
    if os.path.isfile(db_path):
        session['session_id'] = candidate
        logger.info(f"Recovered session from localStorage: {candidate}")
        return True

    logger.info(f"Session recovery failed — no DB file for: {candidate}")
    return False

@app.route('/api/app-config', methods=['GET'])
def get_app_config():
    """Provide frontend configuration settings from CLI arguments"""
    args = app.config['CLI_ARGS']
    
    session_id = session.get('session_id', None)
    superset_user = session.get('superset_user', None)
    
    config = {
        "EXEC_PYTHON_IN_SUBPROCESS": args['exec_python_in_subprocess'],
        "DISABLE_DISPLAY_KEYS": args['disable_display_keys'],
        "DISABLE_DATABASE": args['disable_database'],
        "DISABLE_FILE_UPLOAD": args['disable_file_upload'],
        "PROJECT_FRONT_PAGE": args['project_front_page'],
        "SESSION_ID": session_id,
        "SUPERSET_ENABLED": app.config.get('SUPERSET_ENABLED', False),
        "SSO_LOGIN_URL": (app.config['SUPERSET_URL'].rstrip('/') + '/login/')
                          if app.config.get('SUPERSET_ENABLED') else None,
        "AUTH_USER": {
            "id": superset_user.get("id"),
            "username": superset_user.get("username", ""),
            "first_name": superset_user.get("first_name", ""),
            "last_name": superset_user.get("last_name", ""),
        } if superset_user else None,
    }
    return flask.jsonify(config)

@app.route('/api/tables/<path:path>', methods=['GET', 'POST'])
def database_disabled_fallback(path):
    """Fallback route for table endpoints when database is disabled"""
    if app.config['CLI_ARGS']['disable_database']:
        return flask.jsonify({
            "status": "error",
            "message": "Database functionality is disabled. Use --disable-database=false to enable table operations."
        }), 503
    else:
        # If database is not disabled but we're hitting this route, it means the tables blueprint wasn't registered
        return flask.jsonify({
            "status": "error", 
            "message": "Table routes are not available"
        }), 404


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Data Formulator")
    parser.add_argument("-p", "--port", type=int, default=5000, help="The port number you want to use")
    parser.add_argument("--exec-python-in-subprocess", action='store_true', default=False,
        help="Whether to execute python in subprocess, it makes the app more secure (reducing the chance for the model to access the local machine), but increases the time of response")
    parser.add_argument("--disable-display-keys", action='store_true', default=False,
        help="Whether disable displaying keys in the frontend UI, recommended to turn on if you host the app not just for yourself.")
    parser.add_argument("--disable-database", action='store_true', default=False,
        help="Disable database functionality and table routes. This prevents creation of local database files and disables table-related endpoints.")
    parser.add_argument("--disable-file-upload", action='store_true', default=False,
        help="Disable file upload functionality. This prevents the app from uploading files to the server.")
    parser.add_argument("--project-front-page", action='store_true', default=False,
        help="Project the front page as the main page instead of the app.")
    parser.add_argument("--dev", action='store_true', default=False,
        help="Launch the app in development mode (prevents the app from opening the browser automatically)")
    parser.add_argument("--superset-url", type=str, default=None,
        help="Apache Superset URL for authentication and dataset integration (e.g. http://localhost:8088)")
    return parser.parse_args()


def run_app():
    # Configure logging only when actually running the app
    configure_logging()
    
    args = parse_args()
    # Add this line to make args available to routes
    # override the args from the env file
    app.config['CLI_ARGS'] = {
        'exec_python_in_subprocess': args.exec_python_in_subprocess,
        'disable_display_keys': args.disable_display_keys,
        'disable_database': args.disable_database,
        'disable_file_upload': args.disable_file_upload,
        'project_front_page': args.project_front_page
    }
    
    # Update database manager state
    db_manager._disabled = args.disable_database

    # Late Superset registration when passed via CLI (env var is handled at module level)
    if args.superset_url and not app.config.get('SUPERSET_ENABLED'):
        app.config['SUPERSET_URL'] = args.superset_url
        app.config['SUPERSET_ENABLED'] = True
        from data_formulator.superset.auth_bridge import SupersetAuthBridge
        from data_formulator.superset.superset_client import SupersetClient
        from data_formulator.superset.catalog import SupersetCatalog
        from data_formulator.superset.catalog_routes import catalog_bp
        from data_formulator.superset.data_routes import superset_data_bp

        bridge = SupersetAuthBridge(args.superset_url)
        app.extensions["superset_bridge"] = bridge
        superset_client = SupersetClient(args.superset_url)
        app.extensions["superset_client"] = superset_client
        catalog_ttl = int(os.environ.get('CATALOG_CACHE_TTL', '300'))
        catalog = SupersetCatalog(superset_client, cache_ttl=catalog_ttl)
        app.extensions["superset_catalog"] = catalog
        app.register_blueprint(catalog_bp)
        app.register_blueprint(superset_data_bp)

    if not args.dev:
        url = "http://localhost:{0}".format(args.port)
        threading.Timer(2, lambda: webbrowser.open(url, new=2)).start()

    # Enable debug mode and auto-reload in development mode
    debug_mode = args.dev
    app.run(host='0.0.0.0', port=args.port, debug=debug_mode, use_reloader=debug_mode)

if __name__ == '__main__':
    #app.run(debug=True, host='127.0.0.1', port=5000)
    #use 0.0.0.0 for public
    run_app()
