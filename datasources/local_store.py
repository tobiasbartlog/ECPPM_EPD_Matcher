"""Lokale SQLite-Kopie der Ökobaudat als EPD-Datenquelle."""
import concurrent.futures
from typing import Dict, Any, List, Optional

from config.settings import DataSourceConfig
from datasources.sqlite_schema import connect, EPD_COLUMNS


class LocalEPDStore:
    """Liest EPDs aus einer lokalen SQLite-DB.

    custom-Einträge (source='custom') werden ohne Sonderbehandlung mitgelesen.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or DataSourceConfig.LOCAL_DB_PATH
        self._conn = connect(self._db_path)

    # ------------------------------------------------------------------
    # Public EPDDataSource interface
    # ------------------------------------------------------------------

    def list_epds(
        self,
        labels: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Liest alle EPDs aus der lokalen DB."""
        rows = self._conn.execute(
            "SELECT id, name, klassifizierung, referenzjahr, gueltigkeit, "
            "gliederungsnummer, bauDatRef FROM epds"
        ).fetchall()
        items = [dict(row) for row in rows]

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
        """Lädt vollständige EPD-Einträge für die angegebenen IDs aus der DB."""
        if not epd_ids:
            return []

        placeholders = ",".join("?" * len(epd_ids))
        rows = self._conn.execute(
            f"SELECT id, name, klassifizierung, referenzjahr, gueltigkeit, "
            f"gliederungsnummer, bauDatRef, technischeBeschreibung, anmerkungen, "
            f"anwendungsgebiet, anwendungshinweis FROM epds WHERE id IN ({placeholders})",
            list(epd_ids),
        ).fetchall()
        return [dict(row) for row in rows]

    def count_epds(self) -> int:
        """Zählt alle EPDs in der lokalen DB."""
        row = self._conn.execute("SELECT COUNT(*) FROM epds").fetchone()
        return row[0] if row else 0


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import tempfile
    import os

    print("=" * 70)
    print("LOCAL EPD STORE TEST")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = LocalEPDStore(db_path=db_path)

        # Testdaten: 2 oekobaudat + 1 custom
        store._conn.executemany(
            "INSERT INTO epds (id, name, klassifizierung, technischeBeschreibung, source) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("obd-1", "Asphalttragschicht AC 32", "Asphalt / Tragschichten", "Tragschicht-Text", "oekobaudat"),
                ("obd-2", "Asphaltdeckschicht AC 11", "Asphalt / Deckschichten", "Deckschicht-Text", "oekobaudat"),
                ("custom-1", "Eigener Testdatensatz", "Asphalt / Test", "Eigene Beschreibung", "custom"),
            ],
        )
        store._conn.commit()

        # count_epds == 3
        count = store.count_epds()
        assert count == 3, f"count_epds falsch: {count}"
        print(f"[OK] count_epds() = {count}")

        # list_epds liefert custom-Eintrag mit
        items = store.list_epds()
        ids = {e["id"] for e in items}
        assert "custom-1" in ids, f"custom-1 fehlt: {ids}"
        assert len(items) == 3, f"Anzahl falsch: {len(items)}"
        print(f"[OK] list_epds() = {len(items)} Eintraege (inkl. custom)")

        # get_epd_details liefert Detailfelder
        details = store.get_epd_details(["obd-1", "custom-1"])
        assert len(details) == 2, f"Details Anzahl falsch: {len(details)}"
        detail_map = {d["id"]: d for d in details}
        assert detail_map["custom-1"]["technischeBeschreibung"] == "Eigene Beschreibung", \
            f"Detail-Feld falsch: {detail_map['custom-1']}"
        print("[OK] get_epd_details() liefert Detailfelder korrekt")

    finally:
        store._conn.close()
        os.unlink(db_path)

    print("\nAlle LocalEPDStore-Tests bestanden")
