"""Data routes -- load Superset datasets directly into DF's DuckDB.

Unlike the old gateway approach that proxied through HTTP, this module
writes data directly via the local DuckDB manager.
"""

from __future__ import annotations

import json
import logging
import math
import re

import pandas as pd
from flask import Blueprint, Response, current_app, jsonify, request, session, stream_with_context

from data_formulator.db_manager import db_manager

logger = logging.getLogger(__name__)

superset_data_bp = Blueprint("superset_data", __name__, url_prefix="/api/superset/data")


def _require_auth():
    token = session.get("superset_token")
    user = session.get("superset_user")
    if not token or not user:
        return None, None
    return token, user


def _sanitize_table_name(raw: str) -> str:
    name = (raw or "").lower().replace("-", "_").replace(" ", "_")
    name = re.sub(r"[^\w]", "_", name, flags=re.UNICODE)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or not name[0].isalpha():
        name = f"table_{name}"
    return name


@superset_data_bp.route("/load-dataset", methods=["POST"])
def load_dataset():
    """Fetch data from Superset (RBAC + RLS) and write into the local DuckDB.

    Supports streaming progress via ``"stream": true`` in the request body.
    """
    token, user = _require_auth()
    if not token:
        return jsonify({"status": "error", "message": "Not authenticated"}), 401

    data = request.get_json(force=True)
    dataset_id = data.get("dataset_id")
    row_limit = int(data.get("row_limit", 20_000))
    batch_size = int(data.get("batch_size", min(2000, row_limit)))
    stream_mode = bool(data.get("stream", False))
    table_name_override = (data.get("table_name") or "").strip()

    if not dataset_id:
        return jsonify({"status": "error", "message": "dataset_id required"}), 400

    superset_client = current_app.extensions["superset_client"]
    sid = session["session_id"]

    try:
        detail = superset_client.get_dataset_detail(token, dataset_id)
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Failed to fetch dataset detail: {exc}"}), 500

    db_id = detail["database"]["id"]
    table_name = detail["table_name"]
    schema = detail.get("schema", "")
    dataset_sql = (detail.get("sql") or "").strip()
    dataset_kind = (detail.get("kind") or "").lower()

    if dataset_kind == "virtual" and dataset_sql:
        base_sql = f"SELECT * FROM ({dataset_sql.rstrip(';')}) AS _vds"
    else:
        prefix = f'"{schema}".' if schema else ""
        base_sql = f'SELECT * FROM {prefix}"{table_name}"'

    safe_name = _sanitize_table_name(table_name_override or table_name)

    def _generate():
        total_loaded = 0
        loaded_batches = 0
        columns = []

        try:
            sql_session = superset_client.create_sql_session(token)
            full_sql = f"SELECT * FROM ({base_sql}) AS _src LIMIT {row_limit}"
            result = superset_client.execute_sql_with_session(
                sql_session, db_id, full_sql, schema, row_limit
            )
            all_rows = result.get("data", []) or []
            columns = [c.get("column_name", c.get("name", "")) for c in result.get("columns", [])]

            if all_rows:
                df = pd.DataFrame(all_rows)
                with db_manager.connection(sid) as conn:
                    conn.execute(f"DROP TABLE IF EXISTS \"{safe_name}\"")
                    conn.execute(f"CREATE TABLE \"{safe_name}\" AS SELECT * FROM df")
                total_loaded = len(all_rows)
                loaded_batches = 1

            if stream_mode:
                yield json.dumps({
                    "type": "progress",
                    "loaded_batches": loaded_batches,
                    "total_loaded_rows": total_loaded,
                }, ensure_ascii=False) + "\n"

            done_payload = {
                "status": "ok",
                "table_name": safe_name,
                "row_count": total_loaded,
                "columns": columns,
                "session_id": sid,
            }

            if stream_mode:
                yield json.dumps({"type": "done", **done_payload}, ensure_ascii=False) + "\n"
            else:
                yield json.dumps(done_payload, ensure_ascii=False)

        except Exception as exc:
            import traceback
            logger.error("Failed to load dataset %s: %s\n%s", dataset_id, exc, traceback.format_exc())
            err = {"status": "error", "message": str(exc)}
            if stream_mode:
                yield json.dumps({"type": "error", **err}, ensure_ascii=False) + "\n"
            else:
                yield json.dumps(err, ensure_ascii=False)

    if stream_mode:
        return Response(
            stream_with_context(_generate()),
            content_type="text/x-ndjson; charset=utf-8",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    payload_text = "".join(_generate())
    parsed = json.loads(payload_text)
    status_code = 500 if parsed.get("status") == "error" else 200
    return Response(payload_text, status=status_code, content_type="application/json")
