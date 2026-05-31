"""SQLite-Schema für lokale EPD-Datenbank."""
import sqlite3

# Spalten der epds-Tabelle (exklusive id, source, raw_json)
EPD_COLUMNS = (
    "name", "klassifizierung",
    "referenzjahr", "gueltigkeit", "gliederungsnummer", "bauDatRef",
    "technischeBeschreibung", "anmerkungen",
    "anwendungsgebiet", "anwendungshinweis",
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS epds (
    id                      TEXT PRIMARY KEY,
    name                    TEXT NOT NULL DEFAULT '',
    klassifizierung         TEXT NOT NULL DEFAULT '',
    referenzjahr            TEXT NOT NULL DEFAULT '',
    gueltigkeit             TEXT NOT NULL DEFAULT '',
    gliederungsnummer       TEXT NOT NULL DEFAULT '',
    bauDatRef               TEXT NOT NULL DEFAULT '',
    technischeBeschreibung  TEXT NOT NULL DEFAULT '',
    anmerkungen             TEXT NOT NULL DEFAULT '',
    anwendungsgebiet        TEXT NOT NULL DEFAULT '',
    anwendungshinweis       TEXT NOT NULL DEFAULT '',
    source                  TEXT NOT NULL DEFAULT 'oekobaudat',
    raw_json                TEXT NOT NULL DEFAULT ''
)
"""


def connect(path: str) -> sqlite3.Connection:
    """Öffnet SQLite-Verbindung und stellt Schema sicher."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn
