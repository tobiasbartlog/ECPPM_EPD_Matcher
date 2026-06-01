"""SQLite-Schema für lokale EPD-Datenbank."""
import sqlite3

# Spalten der epds-Tabelle (exklusive id, source, raw_json)
EPD_COLUMNS = (
    "name", "klassifizierung",
    "referenzjahr", "gueltigkeit", "gliederungsnummer", "bauDatRef",
    "technischeBeschreibung", "anmerkungen",
    "anwendungsgebiet", "anwendungshinweis",
    "regNo", "subType",
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
    regNo                   TEXT NOT NULL DEFAULT '',
    subType                 TEXT NOT NULL DEFAULT '',
    source                  TEXT NOT NULL DEFAULT 'oekobaudat',
    raw_json                TEXT NOT NULL DEFAULT ''
)
"""

_MIGRATIONS = [
    "ALTER TABLE epds ADD COLUMN regNo TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE epds ADD COLUMN subType TEXT NOT NULL DEFAULT ''",
]


def connect(path: str) -> sqlite3.Connection:
    """Öffnet SQLite-Verbindung und stellt Schema sicher."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE_SQL)
    _apply_migrations(conn)
    conn.commit()
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Wendet Schema-Migrationen an, die noch nicht im Schema sind."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(epds)")}
    if "regNo" not in existing_cols:
        conn.execute(_MIGRATIONS[0])
    if "subType" not in existing_cols:
        conn.execute(_MIGRATIONS[1])
