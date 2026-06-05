"""Validierung und Anwendung von custom-Einträgen für die local-custom-DB.

Quelle der Wahrheit ist das `custom_entries_config.json`; die `local-custom`-DB ist ein
daraus abgeleitetes, neu-baubares Artefakt (siehe docs/adr/0002-local-custom-datenquelle.md).

Jeder INSERT-Eintrag wird **zwei-stufig fail-fast** validiert, bevor er eingefügt wird:
  1. Tiefbau-Whitelist — `klassifizierung` muss unter einem Tiefbau-Präfix liegen
     (wiederverwendet matching_rules.ist_tiefbau_relevant — keine zweite Quelle der Wahrheit).
  2. Glossar-Filter-Reachability — der Eintrag muss für sein deklariertes
     (ziel_material, ziel_schicht)-Paar als Kandidat durch Stage 3 kommen, sonst wäre er
     eingefügt, aber für das LLM unsichtbar (Migration misst still null).
"""
import json
import shutil
import sqlite3
from typing import Dict, Any, List, Tuple

from matching.matching_rules import ist_tiefbau_relevant
from matching.epd_filter import EPDFilter
from datasources.sqlite_schema import connect

# Pflichtfelder eines INSERT-Eintrags. `quelle` dokumentiert das reale Vorlage-Produkt
# (IBU / EPD Norge / Hersteller); ziel_material + ziel_schicht treiben den Reachability-
# Dry-Run. ziel_schicht ist der **echte Input-NAME** der Zielschicht (z.B.
# "Bituminöse Tragschicht") — bewusst kein Enum, da die realen Schichtnamen von der
# normativen Taxonomie abweichen; das echte Tor ist die Reachability-Prüfung.
INSERT_REQUIRED = ("id", "name", "klassifizierung", "ziel_schicht", "ziel_material", "quelle")

# Spalten der epds-Tabelle, die ein INSERT füllt (Reihenfolge fix für VALUES).
_INSERT_COLS = (
    "id", "name", "klassifizierung",
    "technischeBeschreibung", "anmerkungen",
    "anwendungsgebiet", "anwendungshinweis",
    "referenzjahr", "gueltigkeit", "gliederungsnummer",
    "bauDatRef", "source", "raw_json",
)


class CustomEntryError(ValueError):
    """Ein oder mehrere custom-Einträge haben die Validierung nicht bestanden."""


def _entry_to_epd(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Minimaler EPD-Vertrag aus einem Config-Eintrag (genug für Stage 3)."""
    return {
        "id": entry["id"],
        "name": entry.get("name", ""),
        "klassifizierung": entry.get("klassifizierung", ""),
    }


def _reachability_ok(entry: Dict[str, Any]) -> Tuple[bool, str]:
    """True, wenn der Glossar-Filter den Eintrag für sein ziel-Paar als Kandidat erfasst."""
    epd = _entry_to_epd(entry)
    out, _ = EPDFilter().filter_for_single_material(
        [epd], entry["ziel_material"], entry["ziel_schicht"]
    )
    if any(e.get("id") == entry["id"] for e in out):
        return True, ""
    return False, (
        f"INSERT {entry['id']}: vom Glossar-Filter für "
        f"(Material='{entry['ziel_material']}', Schicht='{entry['ziel_schicht']}') "
        f"nicht als Kandidat erfasst — name/klassifizierung prüfen, sonst bleibt der Eintrag unsichtbar."
    )


def validate_entry(entry: Dict[str, Any]) -> Tuple[bool, str]:
    """Validiert einen einzelnen Config-Eintrag. Gibt (ok, grund) zurück."""
    action = entry.get("action", "insert")

    if action == "update":
        if not entry.get("id"):
            return False, "UPDATE ohne id"
        if not entry.get("fields"):
            return False, f"UPDATE {entry.get('id')}: keine fields angegeben"
        if not entry.get("quelle"):
            return False, f"UPDATE {entry.get('id')}: Pflichtfeld 'quelle' fehlt"
        return True, ""

    if action == "insert":
        missing = [f for f in INSERT_REQUIRED if not entry.get(f)]
        if missing:
            return False, f"INSERT {entry.get('id', '?')}: Pflichtfelder fehlen: {missing}"
        if not ist_tiefbau_relevant(entry):
            return False, (
                f"INSERT {entry['id']}: klassifizierung '{entry['klassifizierung']}' liegt nicht "
                f"unter einem Tiefbau-Whitelist-Präfix — würde von Stage 3 strukturell ausgeschlossen."
            )
        return _reachability_ok(entry)

    return False, f"Unbekannte action '{action}' in Eintrag {entry.get('id', '?')}"


def validate_entries(entries: List[Dict[str, Any]]) -> List[str]:
    """Validiert alle Einträge. Gibt die Liste aller Fehlermeldungen zurück (leer = ok)."""
    errors = []
    for entry in entries:
        ok, grund = validate_entry(entry)
        if not ok:
            errors.append(grund)
    return errors


def apply_entries(conn: sqlite3.Connection, entries: List[Dict[str, Any]]) -> List[str]:
    """Wendet validierte Einträge auf eine offene DB-Verbindung an. Gibt Änderungslog zurück."""
    log = []
    for entry in entries:
        action = entry.get("action", "insert")
        eid = entry["id"]
        note = entry.get("note", "")

        if action == "update":
            fields = entry["fields"]
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(
                f"UPDATE epds SET {set_clause} WHERE id = ?",
                list(fields.values()) + [eid],
            )
            desc = f"UPDATE {eid} ({', '.join(fields.keys())})"

        elif action == "insert":
            vals = [
                eid,
                entry.get("name", ""),
                entry.get("klassifizierung", ""),
                entry.get("technischeBeschreibung", ""),
                entry.get("anmerkungen", ""),
                entry.get("anwendungsgebiet", ""),
                entry.get("anwendungshinweis", ""),
                entry.get("referenzjahr", ""),
                entry.get("gueltigkeit", ""),
                entry.get("gliederungsnummer", ""),
                entry.get("bauDatRef", ""),
                "custom",
                json.dumps(
                    {"id": eid, "name": entry.get("name", ""),
                     "source": "custom", "quelle": entry.get("quelle", "")},
                    ensure_ascii=False,
                ),
            ]
            conn.execute(
                f"INSERT OR REPLACE INTO epds ({', '.join(_INSERT_COLS)}) "
                f"VALUES ({', '.join('?' * len(_INSERT_COLS))})",
                vals,
            )
            desc = f"INSERT {eid} \"{entry.get('name', '')}\" (custom)"
        else:
            continue

        log.append(f"{desc}{' — ' + note if note else ''}")
    return log


def build_custom_db(src_db: str, dst_db: str, entries: List[Dict[str, Any]]) -> List[str]:
    """Baut die local-custom-DB: validiert fail-fast, kopiert src→dst, wendet Einträge an.

    Validierung läuft VOR dem Kopieren — schlägt sie fehl, wird die Platte nicht angefasst
    und keine LLM-Kosten riskiert. Gibt das Änderungslog zurück.
    """
    errors = validate_entries(entries)
    if errors:
        raise CustomEntryError(
            f"{len(errors)} Eintrag/Einträge nicht whitelist-/reachability-konform:\n  - "
            + "\n  - ".join(errors)
        )

    shutil.copy2(src_db, dst_db)
    conn = connect(dst_db)  # stellt Schema/Migrationen auf der Kopie sicher
    try:
        log = apply_entries(conn, entries)
        conn.commit()
    finally:
        conn.close()
    return log


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import tempfile
    import os
    import sys

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("CUSTOM-ENTRIES VALIDATOR TEST")
    print("=" * 70)

    # (Eintrag, erwartet_ok, Begründung) — tabellarisch wie matching_rules-Tests.
    cases = [
        (
            {"action": "insert", "id": "custom-ac11-001",
             "name": "Asphaltdeckschicht AC 11 D S", "ziel_schicht": "Deckschicht",
             "ziel_material": "AC 11 D S", "quelle": "IBU EPD-XYZ",
             "klassifizierung": "Mineralische Baustoffe / Asphalt / Deckschichten"},
            True, "Asphalt-Deckschicht, whitelist-OK, name trägt 'deckschicht'",
        ),
        (
            {"action": "insert", "id": "custom-frost-bad",
             "name": "Kiestragschicht für Frostschutzschicht", "ziel_schicht": "Frostschutzschicht",
             "ziel_material": "Frostschutzschicht 0/63", "quelle": "EPD Norge",
             "klassifizierung": "Mineralische Baustoffe / Ungebundene Tragschichten / Frostschutzschichten"},
            False, "klassifizierung NICHT in Whitelist → muss abgelehnt werden",
        ),
        (
            {"action": "insert", "id": "custom-unreachable",
             "name": "Asphaltbinder AC 16", "ziel_schicht": "Nicht bituminöse Tragschicht",
             "ziel_material": "STSuB 0/45", "quelle": "X",
             "klassifizierung": "Mineralische Baustoffe / Zuschläge / Naturstein"},
            False, "Asphalt-Name in Schotter-Schicht → Kategorie-Konflikt → nicht reachable",
        ),
        (
            {"action": "insert", "id": "custom-missing",
             "name": "Etwas", "klassifizierung": "Mineralische Baustoffe / Asphalt / Deckschichten"},
            False, "Pflichtfelder (ziel_*, quelle) fehlen → abgelehnt",
        ),
        (
            {"action": "update", "id": "obd-existing",
             "fields": {"technischeBeschreibung": "Besser"}, "quelle": "IBU"},
            True, "UPDATE mit fields + quelle → ok",
        ),
    ]

    all_ok = True
    for entry, expected, why in cases:
        ok, grund = validate_entry(entry)
        status = "[OK]" if ok == expected else "[FAIL]"
        if ok != expected:
            all_ok = False
        print(f"\n{status} {entry.get('id')}: ok={ok} (erwartet {expected})")
        print(f"      {why}")
        if grund:
            print(f"      Grund: {grund}")

    # build_custom_db end-to-end gegen eine Mini-Quell-DB
    print("\n" + "-" * 70)
    print("build_custom_db END-TO-END")
    print("-" * 70)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "src.db")
        dst = os.path.join(td, "dst.db")
        c = connect(src)
        c.execute(
            "INSERT INTO epds (id, name, klassifizierung, source) VALUES (?, ?, ?, ?)",
            ("obd-1", "Bestehende Asphalttragschicht", "Mineralische Baustoffe / Asphalt / Tragschichten", "oekobaudat"),
        )
        c.commit()
        c.close()

        good_entry = cases[0][0]
        log = build_custom_db(src, dst, [good_entry])
        check = connect(dst)
        cnt = check.execute("SELECT COUNT(*) FROM epds WHERE source='custom'").fetchone()[0]
        src_still = check.execute("SELECT COUNT(*) FROM epds WHERE source='oekobaudat'").fetchone()[0]
        check.close()
        assert cnt == 1, f"custom-Eintrag fehlt: {cnt}"
        assert src_still == 1, f"oekobaudat-Eintrag verloren: {src_still}"
        print(f"[OK] build_custom_db: {log}")

        # fail-fast: ein schlechter Eintrag bricht ab, dst wird nicht beschrieben
        try:
            build_custom_db(src, os.path.join(td, "never.db"), [cases[1][0]])
            print("[FAIL] CustomEntryError wurde nicht geworfen")
            all_ok = False
        except CustomEntryError as e:
            print(f"[OK] fail-fast greift: {str(e).splitlines()[0]}")

    print("\n" + ("Alle Validator-Tests bestanden" if all_ok else "TESTS FEHLGESCHLAGEN"))
    if not all_ok:
        raise SystemExit(1)
