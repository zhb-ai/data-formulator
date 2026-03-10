"""Two-tier Superset dataset catalog with TTL caching.

Tier 1 -- summary: lightweight list for browsing.
Tier 2 -- detail: full column descriptions, types, extra metadata.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class SupersetCatalog:

    def __init__(self, superset_client: Any, cache_ttl: int = 300):
        self.client = superset_client
        self.cache_ttl = cache_ttl
        self._cache: dict[str, dict] = {}

    # -- tier 1: summary -------------------------------------------------

    def get_catalog_summary(
        self,
        access_token: str,
        user_id: int,
    ) -> list[dict]:
        """Lightweight dataset list (cached per user)."""
        cache_key = f"summary_{user_id}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached["ts"] < self.cache_ttl:
            return cached["data"]

        raw = self.client.list_datasets(access_token)
        datasets: list[dict] = []
        for ds in raw.get("result", []):
            columns = ds.get("columns") or []
            if not columns and ds.get("id") is not None:
                try:
                    detail = self.client.get_dataset_detail(access_token, ds["id"])
                    columns = detail.get("columns") or []
                except Exception:
                    logger.debug("Failed to fetch dataset detail for %s", ds.get("id"), exc_info=True)
            datasets.append(
                {
                    "id": ds["id"],
                    "name": ds.get("table_name") or "",
                    "schema": ds.get("schema") or "",
                    "database": (ds.get("database") or {}).get("database_name", "") or "",
                    "description": ds.get("description") or "",
                    "column_count": len(columns),
                    "column_names": [c.get("column_name") or "" for c in columns],
                    "row_count": ds.get("row_count"),
                }
            )

        self._cache[cache_key] = {"data": datasets, "ts": time.time()}
        return datasets

    # -- tier 2: detail --------------------------------------------------

    def get_dataset_detail(
        self,
        access_token: str,
        dataset_id: int,
    ) -> dict:
        return self.client.get_dataset_detail(access_token, dataset_id)

    # -- dashboards ------------------------------------------------------

    def get_dashboard_summary(
        self,
        access_token: str,
        user_id: int,
    ) -> list[dict]:
        """Lightweight dashboard list (cached per user)."""
        cache_key = f"dashboards_{user_id}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached["ts"] < self.cache_ttl:
            return cached["data"]

        raw = self.client.list_dashboards(access_token)
        dashboards: list[dict] = []
        for db in raw.get("result", []):
            owners = db.get("owners") or []
            dashboards.append(
                {
                    "id": db["id"],
                    "title": db.get("dashboard_title") or "",
                    "slug": db.get("slug") or "",
                    "status": db.get("status") or "published",
                    "url": db.get("url") or "",
                    "changed_on_delta_humanized": db.get("changed_on_delta_humanized") or "",
                    "owners": [
                        (o.get("first_name") or "") + " " + (o.get("last_name") or "")
                        for o in owners
                    ],
                }
            )

        self._cache[cache_key] = {"data": dashboards, "ts": time.time()}
        return dashboards

    def get_dashboard_datasets(
        self,
        access_token: str,
        dashboard_id: int,
    ) -> list[dict]:
        """Return datasets used by a specific dashboard."""
        raw = self.client.get_dashboard_datasets(access_token, dashboard_id)
        datasets: list[dict] = []
        for ds in raw.get("result", []):
            columns = ds.get("columns") or []
            datasets.append(
                {
                    "id": ds.get("id"),
                    "name": ds.get("table_name") or ds.get("name") or "",
                    "schema": ds.get("schema") or "",
                    "database": ((ds.get("database") or {}).get("database_name", "")
                        if isinstance(ds.get("database"), dict)
                        else ds.get("database_name") or "") or "",
                    "description": ds.get("description") or "",
                    "column_count": len(columns),
                    "column_names": [c.get("column_name") or "" for c in columns],
                    "row_count": ds.get("row_count"),
                }
            )
        return datasets

    # -- cache management ------------------------------------------------

    def invalidate(self, user_id: int | None = None) -> None:
        if user_id is not None:
            self._cache.pop(f"summary_{user_id}", None)
            self._cache.pop(f"dashboards_{user_id}", None)
        else:
            self._cache.clear()
