# `local-custom`-Datenquelle und konfigurationsgetriebener DB-Aufbau

Für das Sparse-EPD-Experiment brauchen wir produktspezifische `custom`-Einträge, ohne die
reproduzierbare Datengrundlage der Hauptablation zu verändern. Wir führen einen **vierten**
`EPD_DATA_SOURCE`-Wert `local-custom` ein (eigene DB-Datei `data/oekobaudat_custom.db`, gleicher
`LocalEPDStore`-Code-Pfad wie `local`) und ein eigenständiges `build_custom_db.py`, das die reine
`oekobaudat.db` kopiert, jeden Eintrag aus `custom_entries_config.json` zwei-stufig **fail-fast**
validiert (Tiefbau-Whitelist + Glossar-Filter-Reachability gegen `ziel_schicht`) und dann
`source='custom'` einfügt. Das Vorher/Nachher-Experiment wird damit zum dünnen Orchestrator
(`local` vs. `local-custom`).

## Considered Options

- **Neuer Quellwert `local-custom`** (gewählt) statt nur `LOCAL_DB_PATH` auf eine andere Datei
  zeigen: macht im Run-Provenance explizit, gegen welchen Korpus gematcht wurde, und erlaubt, `local`
  im Glossar sauber als „reine Download-Kopie" zu schärfen.
- **`custom_entries_config.json` als Quelle der Wahrheit** statt der DB: die `local-custom`-DB ist ein
  abgeleitetes, idempotent neu-baubares Artefakt; der eingecheckte Config (inkl. Pflichtfeld `quelle`
  mit realer Produkt-EPD-Vorlage) ist der Audit-Trail fürs Paper.
- **Whitelist + Reachability-Dry-Run** statt nur Whitelist (PRD-Scope): fängt den teuren Fehlermodus
  „Eintrag eingefügt, aber vom Glossar-Filter nie als Kandidat gesehen → Migration misst still null"
  ab, bevor LLM-Kosten anfallen.

## Consequences

- Synthetische `custom-`-IDs sind bewusst **nicht** LCA-auflösbar; die Einträge sind reine
  Forschungsartefakte für die Migrationsmessung (zirkularitäts-robust), nicht für echte
  Ökobilanz-Hochrechnung gedacht.
- Wird die `oekobaudat.db` neu heruntergeladen, ist die `local-custom`-DB stale und muss via
  `build_custom_db.py` neu gebaut werden.
- Jeder INSERT-Config-Eintrag braucht `ziel_schicht` (der echte Input-NAME der Zielschicht,
  z.B. „Bituminöse Tragschicht") und `ziel_material` für den Reachability-Dry-Run. Bewusst kein
  Taxonomie-Enum, da die realen Schichtnamen davon abweichen — das echte Tor ist die Reachability.
