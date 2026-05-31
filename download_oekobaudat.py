"""Lädt die Ökobaudat einmalig in eine lokale SQLite-DB.

Verwendung:
    python download_oekobaudat.py [--db-path data/oekobaudat.db]
                                   [--with-details]
                                   [--max-workers 10]

Eigene Einträge mit source='custom' werden nicht überschrieben.
"""
import argparse
import json
import os
import sys
import concurrent.futures
from typing import Dict, Any, List

from config.settings import DataSourceConfig
from datasources.oekobaudat_client import OekobaudatClient
from datasources.oekobaudat_mapping import map_detail
from datasources.sqlite_schema import connect, EPD_COLUMNS


def _upsert(conn, epd: Dict[str, Any], source: str = "oekobaudat") -> None:
    """Schreibt oder aktualisiert einen EPD-Eintrag; custom-Einträge bleiben unberührt."""
    existing = conn.execute(
        "SELECT source FROM epds WHERE id = ?", (epd["id"],)
    ).fetchone()

    if existing and existing["source"] == "custom":
        return  # custom-Einträge nie überschreiben

    columns = ("id",) + EPD_COLUMNS + ("source", "raw_json")
    placeholders = ", ".join("?" * len(columns))
    col_names = ", ".join(columns)
    updates = ", ".join(f"{c} = excluded.{c}" for c in EPD_COLUMNS + ("source", "raw_json"))

    values = [epd.get("id") or ""]
    for col in EPD_COLUMNS:
        values.append(str(epd.get(col) or ""))
    values.append(source)
    values.append(json.dumps(epd, ensure_ascii=False))

    conn.execute(
        f"INSERT INTO epds ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        values,
    )


def _fetch_and_merge_detail(
    client: OekobaudatClient,
    list_item: Dict[str, Any],
) -> Dict[str, Any]:
    """Lädt ILCD-Detail für eine UUID und mergt mit Listen-Eintrag."""
    try:
        raw = client._fetch_detail(list_item["id"])
        if raw:
            detail = map_detail(raw)
            # Listen-Eintrag hat referenzjahr/gueltigkeit/gliederungsnummer
            return {**detail, **{
                k: list_item[k]
                for k in ("id", "name", "klassifizierung", "referenzjahr", "gueltigkeit", "gliederungsnummer")
                if list_item.get(k)
            }}
    except Exception as exc:
        print(f"  ⚠️ Detail-Fehler für {list_item['id']}: {exc}")
    return list_item


def main(args: argparse.Namespace) -> None:
    db_path = args.db_path
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    print(f"\n{'='*70}")
    print("ÖKOBAUDAT DOWNLOAD")
    print(f"{'='*70}")
    print(f"  Ziel-DB:     {db_path}")
    print(f"  Details:     {'ja' if args.with_details else 'nein'}")
    print(f"  Workers:     {args.max_workers}")
    if DataSourceConfig.OEKOBAUDAT_CLASSIFICATION:
        print(f"  Klasse:      {DataSourceConfig.OEKOBAUDAT_CLASSIFICATION}")
    print()

    client = OekobaudatClient()
    conn = connect(db_path)

    # 1. Katalog zählen
    total = client.count_epds()
    print(f"📊 Katalog: {total} Prozesse")

    # 2. Liste laden
    print("📥 Lade EPD-Liste...")
    items = client.list_epds()
    print(f"✅ {len(items)} Einträge geladen")

    if not items:
        print("⚠️ Keine Einträge gefunden. Abbruch.")
        sys.exit(0)

    # 3. Optional: Details laden und mergen
    if args.with_details:
        print(f"\n📥 Lade Details (parallel, {args.max_workers} Workers)...")
        enriched: List[Dict[str, Any]] = []
        errors = 0
        done = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as ex:
            futures = {
                ex.submit(_fetch_and_merge_detail, client, item): item
                for item in items
            }
            for future in concurrent.futures.as_completed(futures):
                done += 1
                if done % max(1, len(items) // 20) == 0 or done == len(items):
                    print(f"  Progress: {done}/{len(items)}")
                try:
                    enriched.append(future.result())
                except Exception as exc:
                    errors += 1
                    if errors <= 3:
                        print(f"  ⚠️ {exc}")
        if errors:
            print(f"  ⚠️ {errors} Detail-Fehler")
        items = enriched

    # 4. Eintragen
    print(f"\n💾 Schreibe {len(items)} Einträge in DB...")
    written = 0
    for item in items:
        if not item.get("id"):
            continue
        _upsert(conn, item)
        written += 1

    conn.commit()

    custom_count = conn.execute(
        "SELECT COUNT(*) FROM epds WHERE source = 'custom'"
    ).fetchone()[0]
    total_db = conn.execute("SELECT COUNT(*) FROM epds").fetchone()[0]

    print(f"✅ Fertig. DB enthält {total_db} Einträge ({custom_count} custom, unberührt).")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ökobaudat → lokale SQLite-DB")
    parser.add_argument(
        "--db-path",
        default=DataSourceConfig.LOCAL_DB_PATH,
        help=f"Pfad zur SQLite-DB (Standard: {DataSourceConfig.LOCAL_DB_PATH})",
    )
    parser.add_argument(
        "--with-details",
        action="store_true",
        help="Detail-Texte (technischeBeschreibung etc.) mit herunterladen",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Parallele HTTP-Verbindungen für Detail-Download (Standard: 10)",
    )
    main(parser.parse_args())
