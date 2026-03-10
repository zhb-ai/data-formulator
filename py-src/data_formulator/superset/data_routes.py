"""Data routes -- load Superset datasets directly into DF's DuckDB.

Unlike the old gateway approach that proxied through HTTP, this module
writes data directly via the local DuckDB manager.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import re
import time

import pandas as pd
from flask import Blueprint, Response, current_app, jsonify, request, session, stream_with_context
from requests.exceptions import HTTPError

from data_formulator.db_manager import db_manager

logger = logging.getLogger(__name__)

superset_data_bp = Blueprint("superset_data", __name__, url_prefix="/api/superset/data")


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


def _sanitize_table_name(raw: str) -> str:
    name = (raw or "").lower().replace("-", "_").replace(" ", "_")
    name = re.sub(r"[^\w]", "_", name, flags=re.UNICODE)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or not name[0].isalpha():
        name = f"table_{name}"
    return name


def _quote_identifier(name: str) -> str:
    escaped = (name or "").replace('"', '""')
    return f'"{escaped}"'


def _column_ref(name: str) -> str:
    stripped = (name or "").strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped):
        return stripped
    return _quote_identifier(stripped)


def _sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _build_dataset_sql(detail: dict) -> tuple[int, str, str]:
    db_id = detail["database"]["id"]
    table_name = detail["table_name"]
    schema = detail.get("schema", "") or ""
    dataset_sql = (detail.get("sql") or "").strip()
    dataset_kind = (detail.get("kind") or "").lower()

    if dataset_kind == "virtual" and dataset_sql:
        return db_id, schema, f"SELECT * FROM ({dataset_sql.rstrip(';')}) AS _vds"

    prefix = f'"{schema}".' if schema else ""
    return db_id, schema, f'SELECT * FROM {prefix}"{table_name}"'


def _build_where_clauses(filters: list[dict], valid_columns: set[str]) -> list[str]:
    clauses: list[str] = []
    allowed_ops = {
        "IN",
        "NOT_IN",
        "EQ",
        "NEQ",
        "GT",
        "GTE",
        "LT",
        "LTE",
        "BETWEEN",
        "LIKE",
        "ILIKE",
        "IS_NULL",
        "IS_NOT_NULL",
    }
    compare_op_map = {
        "EQ": "=",
        "NEQ": "!=",
        "GT": ">",
        "GTE": ">=",
        "LT": "<",
        "LTE": "<=",
        "LIKE": "LIKE",
        "ILIKE": "ILIKE",
    }

    for raw_filter in filters:
        if not isinstance(raw_filter, dict):
            raise ValueError("Invalid filter payload")
        column = (raw_filter.get("column") or raw_filter.get("column_name") or "").strip()
        operator = str(raw_filter.get("operator") or "").upper()
        value = raw_filter.get("value")
        if not column or operator not in allowed_ops:
            raise ValueError(f"Invalid filter definition: {raw_filter}")
        if column not in valid_columns:
            raise ValueError(f"Unknown filter column: {column}")

        quoted_column = _column_ref(column)
        if operator == "IS_NULL":
            clauses.append(f"{quoted_column} IS NULL")
            continue
        if operator == "IS_NOT_NULL":
            clauses.append(f"{quoted_column} IS NOT NULL")
            continue
        if operator in {"IN", "NOT_IN"}:
            values = value if isinstance(value, list) else [value]
            values = [v for v in values if v not in (None, "")]
            if not values:
                continue
            joined = ", ".join(_sql_literal(v) for v in values)
            keyword = "NOT IN" if operator == "NOT_IN" else "IN"
            clauses.append(f"{quoted_column} {keyword} ({joined})")
            continue
        if operator == "BETWEEN":
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError(f"BETWEEN requires two values for column {column}")
            if value[0] in (None, "") or value[1] in (None, ""):
                continue
            clauses.append(
                f"{quoted_column} BETWEEN {_sql_literal(value[0])} AND {_sql_literal(value[1])}"
            )
            continue

        if value in (None, ""):
            continue
        if operator in {"LIKE", "ILIKE"}:
            text_value = str(value)
            if "%" not in text_value and "_" not in text_value:
                text_value = f"%{text_value}%"
            clauses.append(f"{quoted_column} {compare_op_map[operator]} {_sql_literal(text_value)}")
            continue
        clauses.append(f"{quoted_column} {compare_op_map[operator]} {_sql_literal(value)}")

    return clauses


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
    filters = data.get("filters") or []

    if not dataset_id:
        return jsonify({"status": "error", "message": "dataset_id required"}), 400

    superset_client = current_app.extensions["superset_client"]
    sid = session["session_id"]

    try:
        detail = superset_client.get_dataset_detail(token, dataset_id)
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            logger.info("Superset API 返回 401，尝试刷新 token 后重试")
            token = _try_refresh()
            if token:
                try:
                    detail = superset_client.get_dataset_detail(token, dataset_id)
                except Exception as retry_err:
                    return jsonify({"status": "error", "message": f"Superset 认证失败，请重新登录: {retry_err}"}), 401
            else:
                return jsonify({"status": "error", "message": "Superset 认证已过期，请重新登录"}), 401
        else:
            return jsonify({"status": "error", "message": f"Failed to fetch dataset detail: {exc}"}), 502
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Failed to fetch dataset detail: {exc}"}), 500

    db_id, schema, base_sql = _build_dataset_sql(detail)
    table_name = detail["table_name"]
    valid_columns = {
        (column.get("column_name") or column.get("name") or "")
        for column in (detail.get("columns") or [])
        if (column.get("column_name") or column.get("name") or "")
    }
    try:
        where_clauses = _build_where_clauses(filters, valid_columns)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    safe_name = _sanitize_table_name(table_name_override or table_name)

    def _generate():
        total_loaded = 0
        loaded_batches = 0
        columns = []

        try:
            sql_session = superset_client.create_sql_session(token)
            where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            full_sql = f"SELECT * FROM ({base_sql}) AS _src{where_sql} LIMIT {row_limit}"
            logger.info(
                "Superset filtered load dataset_id=%s filters=%s sql=%s",
                dataset_id,
                filters,
                full_sql,
            )
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
