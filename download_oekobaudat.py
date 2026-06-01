"""Lädt die Ökobaudat einmalig in eine lokale SQLite-DB.

Verwendung:
    python download_oekobaudat.py [--db-path data/oekobaudat.db]
                                   [--with-details]
                                   [--max-workers 10]
                                   [--clean]
                                   [--all-versions]

Standardverhalten: Deduplizierung auf neueste Versionen.
  - Eintraege MIT regNo: neueste Version pro regNo (max refYear)
  - Eintraege OHNE regNo (Sphera/GaBi-Generika, z.B. Asphalt-EPDs):
    neueste Version pro (Name + ClassificId)

--all-versions     Deduplication deaktivieren, alle Eintraege laden.
--clean            Alle source='oekobaudat'-Eintraege loeschen bevor neu
                   eingefuegt wird (sauberer Neuaufbau der DB).

Eigene Eintraege mit source='custom' werden nie ueberschrieben.
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
            # Listen-Eintrag hat referenzjahr/gueltigkeit/gliederungsnummer/regNo
            return {**detail, **{
                k: list_item[k]
                for k in ("id", "name", "klassifizierung", "referenzjahr",
                          "gueltigkeit", "gliederungsnummer", "regNo")
                if list_item.get(k)
            }}
    except Exception as exc:
        print(f"  Detail-Fehler fuer {list_item['id']}: {exc}")
    return list_item


def _select_latest_epds(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupliziert EPD-Liste auf neueste Versionen.

    Zwei Strategien parallel:
    - Mit regNo: neueste Version pro regNo (max refYear, Tiebreaker max gueltigkeit)
    - Ohne regNo (Sphera/GaBi-Generika): neueste Version pro (Name, ClassificId)

    Kein Subtype-Filter: Asphalt-EPDs sind 'generic dataset' ohne regNo und
    müssen erhalten bleiben.
    """
    from collections import defaultdict

    by_regno: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_name_class: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

    for item in items:
        rn = str(item.get("regNo") or "").strip()
        if rn:
            by_regno[rn].append(item)
        else:
            name_key = str(item.get("name") or "").lower().strip()
            class_key = str(item.get("gliederungsnummer") or "").strip()
            by_name_class[(name_key, class_key)].append(item)

    def _best(group: List[Dict[str, Any]]) -> Dict[str, Any]:
        return max(group, key=lambda i: (
            str(i.get("referenzjahr") or ""),
            str(i.get("gueltigkeit") or ""),
        ))

    selected = []
    skipped_regno = 0
    skipped_generic = 0

    for group in by_regno.values():
        selected.append(_best(group))
        skipped_regno += len(group) - 1

    for group in by_name_class.values():
        selected.append(_best(group))
        skipped_generic += len(group) - 1

    print(f"  Deduplizierung: {len(items)} -> {len(selected)} Eintraege")
    print(f"  Verworfen: {skipped_regno} aeltere regNo-Versionen, "
          f"{skipped_generic} aeltere generische Versionen")
    return selected


def main(args: argparse.Namespace) -> None:
    db_path = args.db_path
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    print(f"\n{'='*70}")
    print("OEKOBAUDAT DOWNLOAD")
    print(f"{'='*70}")
    print(f"  Ziel-DB:         {db_path}")
    print(f"  Stock:           {DataSourceConfig.OEKOBAUDAT_STOCK_ID or '(alle Stocks – historische Union)'}")
    print(f"  Details:         {'ja' if args.with_details else 'nein'}")
    print(f"  Workers:         {args.max_workers}")
    print(f"  Deduplizierung:  {'nein (--all-versions)' if args.all_versions else 'ja (neueste pro regNo)'}")
    print(f"  Clean-Rebuild:   {'ja (--clean)' if args.clean else 'nein'}")
    if DataSourceConfig.OEKOBAUDAT_CLASSIFICATION:
        print(f"  Klasse:          {DataSourceConfig.OEKOBAUDAT_CLASSIFICATION}")
    print()

    client = OekobaudatClient()
    conn = connect(db_path)

    # 1. Optional: DB leeren
    if args.clean:
        deleted = conn.execute("DELETE FROM epds WHERE source = 'oekobaudat'").rowcount
        conn.commit()
        print(f"DB geleert: {deleted} oekobaudat-Eintraege entfernt.\n")

    # 2. Katalog zählen
    total = client.count_epds()
    print(f"Katalog: {total} Prozesse laut API")

    # 3. Liste laden
    print("Lade EPD-Liste...")
    items = client.list_epds()
    print(f"{len(items)} Eintraege geladen")

    if not items:
        print("Keine Eintraege gefunden. Abbruch.")
        sys.exit(0)

    # 4. Deduplizierung: neueste Version pro regNo / pro (Name+ClassificId)
    if not args.all_versions:
        items = _select_latest_epds(items)

    # 5. Optional: Details laden und mergen
    if args.with_details:
        print(f"\nLade Details (parallel, {args.max_workers} Workers)...")
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
                        print(f"  {exc}")
        if errors:
            print(f"  {errors} Detail-Fehler")
        items = enriched

    # 6. Eintragen
    print(f"\nSchreibe {len(items)} Eintraege in DB...")
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

    print(f"Fertig. DB enthaelt {total_db} Eintraege ({custom_count} custom, unberuehrt).")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Oekobaudat -> lokale SQLite-DB")
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
        help="Parallele HTTP-Verbindungen fuer Detail-Download (Standard: 10)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Alle oekobaudat-Eintraege vor dem Download loeschen (sauberer Neuaufbau)",
    )
    parser.add_argument(
        "--all-versions",
        action="store_true",
        help="Deduplication deaktivieren und alle Versionen laden",
    )
    main(parser.parse_args())
