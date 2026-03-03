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
                    "name": ds.get("table_name", ""),
                    "schema": ds.get("schema", ""),
                    "database": (ds.get("database") or {}).get("database_name", ""),
                    "description": ds.get("description", "") or "",
                    "column_count": len(columns),
                    "column_names": [c.get("column_name", "") for c in columns],
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

    # -- cache management ------------------------------------------------

    def invalidate(self, user_id: int | None = None) -> None:
        if user_id is not None:
            self._cache.pop(f"summary_{user_id}", None)
        else:
            self._cache.clear()
