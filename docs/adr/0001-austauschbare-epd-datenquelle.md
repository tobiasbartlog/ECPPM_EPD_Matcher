# Austauschbare EPD-Datenquelle

Die alte JWT-API ist tot, fürs Paper soll die Ökobaudat genutzt werden. Wir führen eine
schmale Datenquellen-Naht ein: `AzureEPDMatcher` baut seine Quelle über
`create_data_source()` (Factory), gewählt per `EPD_DATA_SOURCE` ∈ `{online, oekobaudat, local}`.
Alle drei erfüllen denselben EPD-Vertrag (`list_epds` / `get_epd_details` / `count_epds`),
sodass `prompt_builder`, `epd_filter`, `asphalt_glossar` und `main` unverändert bleiben.

Bewusste Entscheidungen und ihre Gründe:

- **Toten `online`-Modus erhalten** statt löschen — er ist der bestehende Vertragsbeweis und
  macht den Schalter testbar; Konstruktion erfolgt **lazy** in der Factory, weil
  `TokenManager` ohne Zugangsdaten im Konstruktor `ValueError` wirft.
- **`local` (SQLite) ist der empfohlene Pfad** für wiederholte Versuche; `oekobaudat` (live)
  zieht 5720 Datensätze pro Lauf und ist für Stichproben gedacht. Detail-Matching nur
  sinnvoll mit `local`, da Details sonst pro `uuid` einzeln per HTTP geladen werden.
- **Frisches, vertrags-benanntes DB-Schema** statt Wiederverwendung des Referenz-Schemas
  (`EPDMatcher_modular`) — macht `local` 1:1 zum Vertrag und selbst-enthaltend; Preis ist
  ein einmaliger Download statt Drop-in der bestehenden 2885-Zeilen-DB.
- **Mapping in einem reinen Modul** (`oekobaudat_mapping.py`) isoliert: der deutsche
  `classific`-Pfad der soda4LCA-Liste wird auf `klassifizierung` gemappt (kritisch für den
  Glossar-Filter), die verschachtelten, sprach-getaggten ILCD-Detailfelder über eine
  robuste `lang=="de"`-Extraktion mit Fallbacks.

## Verworfene Alternative

Die `MAX_EPD_IN_PROMPT`-Kappung vor dem Glossar-Filter (azure_matcher) **nicht** umsortiert,
sondern per Config entschärft (Cap hochsetzen + serverseitiger `OEKOBAUDAT_CLASSIFICATION`-
Filter über `classId`), um die Matcher-Logik außerhalb der Naht unberührt zu lassen.
