"""Baut die local-custom-DB aus der reinen local-DB + custom_entries_config.json.

Quelle der Wahrheit ist das Config-JSON; die erzeugte DB ist ein abgeleitetes, idempotent
neu-baubares Artefakt (siehe docs/adr/0002-local-custom-datenquelle.md).

Verwendung:
    python build_custom_db.py --config benchmark/custom_entries_config.json
    python build_custom_db.py --config <cfg> --src-db data/oekobaudat.db --dst-db data/oekobaudat_custom.db

Ablauf:
  1. Jeder Eintrag wird fail-fast validiert (Tiefbau-Whitelist + Glossar-Filter-Reachability),
     BEVOR die Platte angefasst wird.
  2. src-DB wird nach dst-DB kopiert.
  3. custom-Einträge (source='custom') werden eingefügt/aktualisiert.

Danach: EPD_DATA_SOURCE=local-custom wählt die erzeugte DB.
"""
import argparse
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from config.settings import DataSourceConfig
from datasources.custom_entries import build_custom_db, CustomEntryError


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baut die local-custom-DB aus reiner DB + custom-Einträgen."
    )
    parser.add_argument(
        "--config", required=True, type=Path,
        help="Pfad zu custom_entries_config.json",
    )
    parser.add_argument(
        "--src-db", default=DataSourceConfig.LOCAL_DB_PATH,
        help=f"Reine Quell-DB (Standard: {DataSourceConfig.LOCAL_DB_PATH})",
    )
    parser.add_argument(
        "--dst-db", default=DataSourceConfig.LOCAL_CUSTOM_DB_PATH,
        help=f"Ziel-DB für die Kopie (Standard: {DataSourceConfig.LOCAL_CUSTOM_DB_PATH})",
    )
    args = parser.parse_args()

    if not Path(args.src_db).exists():
        print(f"FEHLER: Quell-DB nicht gefunden: {args.src_db}")
        print("        Zuerst 'python download_oekobaudat.py' ausführen.")
        sys.exit(1)

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    entries = cfg.get("entries", [])

    print(f"\n{'=' * 70}")
    print("BUILD LOCAL-CUSTOM DB")
    print(f"{'=' * 70}")
    print(f"  Config:   {args.config}  ({len(entries)} Einträge)")
    print(f"  Quell-DB: {args.src_db}")
    print(f"  Ziel-DB:  {args.dst_db}")
    print()

    try:
        log = build_custom_db(args.src_db, args.dst_db, entries)
    except CustomEntryError as exc:
        print("VALIDIERUNG FEHLGESCHLAGEN — DB nicht verändert:\n")
        print(exc)
        sys.exit(1)

    print("Angewendete Änderungen:")
    for line in log:
        print(f"  {line}")

    print(f"\nFertig. local-custom-DB gebaut: {args.dst_db}")
    print("Auswahl im Lauf: EPD_DATA_SOURCE=local-custom")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
