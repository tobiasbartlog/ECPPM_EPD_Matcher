"""Live-Abfrage der Ökobaudat über die soda4LCA-REST-API."""
import concurrent.futures
from typing import Dict, Any, List, Optional

import requests

from config.settings import DataSourceConfig
from datasources.oekobaudat_mapping import map_list_item, map_detail


class OekobaudatClient:
    """Lädt EPDs von der öffentlichen soda4LCA-REST-API der Ökobaudat."""

    def __init__(self):
        self._base = DataSourceConfig.OEKOBAUDAT_BASE_URL.rstrip("/")
        self._page_size = DataSourceConfig.OEKOBAUDAT_PAGE_SIZE
        self._class_id = DataSourceConfig.OEKOBAUDAT_CLASSIFICATION
        self._class_system = DataSourceConfig.OEKOBAUDAT_CLASS_SYSTEM

    # ------------------------------------------------------------------
    # Public EPDDataSource interface
    # ------------------------------------------------------------------

    def list_epds(
        self,
        labels: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Lädt alle EPDs paged vom Listen-Endpunkt."""
        items = self._fetch_all_pages()

        if labels:
            items = [
                e for e in items
                if any(
                    lbl.lower() in (e.get("name", "") + " " + e.get("klassifizierung", "")).lower()
                    for lbl in labels
                )
            ]
        return items

    def get_epd_details(
        self,
        epd_ids: List[str],
        max_workers: int = 10,
    ) -> List[Dict[str, Any]]:
        """Lädt ILCD-Detail für jede UUID, parallel."""
        total = len(epd_ids)
        print(f"📥 Lade Details für {total} Ökobaudat-EPDs (parallel, {max_workers} Workers)...")
        results = []
        errors = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            future_to_id = {ex.submit(self._fetch_detail, uid): uid for uid in epd_ids}
            done = 0
            for future in concurrent.futures.as_completed(future_to_id):
                done += 1
                if done % max(1, total // 10) == 0 or done == total:
                    print(f"  Progress: {done}/{total}")
                try:
                    detail = future.result()
                    if detail:
                        results.append(map_detail(detail))
                    else:
                        errors += 1
                except Exception as exc:
                    uid = future_to_id[future]
                    errors += 1
                    if errors <= 3:
                        print(f"  ⚠️ Fehler bei {uid}: {exc}")

        if errors:
            print(f"  ⚠️ {errors} Fehler beim Detail-Laden")
        print(f"✅ {len(results)} Detail-Einträge geladen\n")
        return results

    def count_epds(self) -> int:
        """Gibt totalCount aus dem ersten Page-Response zurück — ohne Vollscan."""
        params = self._base_params()
        params["pageSize"] = 1
        params["startIndex"] = 0
        data = self._get(f"{self._base}/processes", params)
        return int(data.get("totalCount") or 0)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _base_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {"format": "json"}
        if self._class_id:
            params["search"] = "true"
            params["classId"] = self._class_id
            params["classSystem"] = self._class_system
        return params

    def _fetch_all_pages(self) -> List[Dict[str, Any]]:
        start = 0
        all_items: List[Dict[str, Any]] = []

        while True:
            params = self._base_params()
            params["pageSize"] = self._page_size
            params["startIndex"] = start

            data = self._get(f"{self._base}/processes", params)
            page = data.get("data") or []
            total = int(data.get("totalCount") or 0)

            for row in page:
                all_items.append(map_list_item(row))

            start += len(page)
            if start >= total or not page:
                break

        return all_items

    def _fetch_detail(self, uuid: str) -> Optional[Dict[str, Any]]:
        url = f"{self._base}/processes/{uuid}"
        data = self._get(url, {"format": "json", "view": "extended"})
        return data or None

    @staticmethod
    def _get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result if isinstance(result, dict) else {}


# =============================================================================
# TEST (Paging mit gemockten HTTP-Antworten)
# =============================================================================

if __name__ == "__main__":
    from unittest.mock import patch, MagicMock
    import json

    print("=" * 70)
    print("OEKOBAUDAT CLIENT TEST (gemockt)")
    print("=" * 70)

    page1 = {
        "totalCount": 3,
        "pageSize": 2,
        "startIndex": 0,
        "data": [
            {"uuid": "id-1", "name": "EPD Eins", "classific": "Asphalt / Tragschichten", "refYear": "2020", "validUntil": "2025", "classificId": "6.2"},
            {"uuid": "id-2", "name": "EPD Zwei", "classific": "Asphalt / Deckschichten", "refYear": "2020", "validUntil": "2025", "classificId": "6.3"},
        ],
    }
    page2 = {
        "totalCount": 3,
        "pageSize": 2,
        "startIndex": 2,
        "data": [
            {"uuid": "id-3", "name": "EPD Drei", "classific": "Asphalt / Binderschichten", "refYear": "2021", "validUntil": "2026", "classificId": "6.4"},
        ],
    }

    call_log = [0]  # mutable counter für closure
    def mock_get(url, params=None, timeout=60):
        call_log[0] += 1
        start = int((params or {}).get("startIndex", 0))
        page_size = int((params or {}).get("pageSize", 2))
        if page_size == 1:
            data = {"totalCount": 3, "data": []}
        elif start == 0:
            data = page1
        elif start == 2:
            data = page2
        else:
            data = {"totalCount": 3, "data": []}
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    with patch("requests.get", side_effect=mock_get):
        client = OekobaudatClient()

        # count_epds nutzt totalCount ohne Vollscan
        calls_before = call_log[0]
        count = client.count_epds()
        assert count == 3, f"count_epds falsch: {count}"
        assert call_log[0] == calls_before + 1, "count_epds sollte nur 1 Request machen"
        print(f"[OK] count_epds() = {count} (1 Request)")

        # list_epds liefert alle 3 Eintraege ueber 2 Seiten
        items = client.list_epds()
        assert len(items) == 3, f"list_epds Anzahl falsch: {len(items)}"
        ids = {e["id"] for e in items}
        assert ids == {"id-1", "id-2", "id-3"}, f"IDs falsch: {ids}"
        print(f"[OK] list_epds() = {len(items)} Eintraege (Paging korrekt)")

    print("\nAlle Client-Tests bestanden")
