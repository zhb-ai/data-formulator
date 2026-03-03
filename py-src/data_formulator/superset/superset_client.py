"""Thin wrapper around the Superset public REST API."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class SupersetClient:
    """Every Superset API call goes through this class so that upstream
    changes only require edits in one place."""

    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    # -- datasets --------------------------------------------------------

    def list_datasets(
        self,
        access_token: str,
        page: int = 0,
        page_size: int = 100,
    ) -> dict:
        """Return datasets the current user can see (DatasourceFilter)."""
        resp = requests.get(
            f"{self.base_url}/api/v1/dataset/",
            headers=self._headers(access_token),
            params={
                "q": f"(page:{page},page_size:{page_size})",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_dataset_detail(self, access_token: str, dataset_id: int) -> dict:
        resp = requests.get(
            f"{self.base_url}/api/v1/dataset/{dataset_id}",
            headers=self._headers(access_token),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("result", {})

    # -- SQL Lab ---------------------------------------------------------

    def get_csrf_token(self, access_token: str) -> str:
        resp = requests.get(
            f"{self.base_url}/api/v1/security/csrf_token/",
            headers=self._headers(access_token),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("result", "")

    def create_sql_session(self, access_token: str) -> requests.Session:
        """Create a reusable SQL Lab session with auth + CSRF prepared."""
        sql_session = requests.Session()
        sql_session.headers.update(self._headers(access_token))

        csrf_resp = sql_session.get(
            f"{self.base_url}/api/v1/security/csrf_token/",
            timeout=self.timeout,
        )
        csrf_resp.raise_for_status()
        csrf = csrf_resp.json().get("result", "")
        if csrf:
            sql_session.headers.update({"X-CSRFToken": csrf})
        return sql_session

    def execute_sql_with_session(
        self,
        sql_session: requests.Session,
        database_id: int,
        sql: str,
        schema: str = "",
        row_limit: int = 100_000,
    ) -> dict:
        """Execute SQL via an existing session."""
        resp = sql_session.post(
            f"{self.base_url}/api/v1/sqllab/execute/",
            json={
                "database_id": database_id,
                "sql": sql,
                "schema": schema,
                "runAsync": False,
                "queryLimit": row_limit,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()
