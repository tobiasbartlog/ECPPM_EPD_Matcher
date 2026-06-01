# EC3 EPD-Matcher

Ordnet Bau-Materialschichten aus BIM/IFC-Modellen (v.a. deutscher Straßenbau) den passenden
**EPD-Datensätzen** der ÖKOBAUDAT zu — über eine konfigurierbare, fünfstufige Pipeline aus
regelbasierter Vorfilterung und LLM-Matching. Begleitcode zum Paper *„Implementation of an
LLM-based Method for EPD Matching in BIM Workflows“* (EC³ 2026).

---

## Was das Tool macht

Im Ökobilanz-Workflow für Infrastruktur muss jede Bauschicht (z.B. *„Asphaltdeckschicht, AC 11 D
S“*) mit einer **Environmental Product Declaration (EPD)** verknüpft werden, damit ein
nachgelagertes LCA-Tool die Umweltwirkung berechnen kann. Diese Zuordnung ist mühsam, weil die
Praxis-Bezeichnungen (TL Asphalt-StB) und die ÖKOBAUDAT-Datensätze nicht standardisiert
zueinander passen.

Das Tool ist der zentrale Knoten zwischen vier Systemen:

```
   CDE  ──input.json──▶  EPD-Matcher  ──▶ EPD-Datenquelle (ÖKOBAUDAT)
 (BIM/IFC)                   │
                            ▼
                       output.json ──▶  LCA-Tool
                  (Schichten + EPD-UUIDs + Confidence)
```

- **CDE** (Common Data Environment): liefert pro Bauschicht `NAME`, `MATERIAL`, `GUID`-Liste und
  `Volumen` als `input.json`.
- **EPD-Matcher** (dieses Repo): findet je Schicht die besten EPD-Kandidaten.
- **EPD-Datenquelle**: ÖKOBAUDAT (live, lokal, oder die alte Online-API) — austauschbar.
- **LCA-Tool**: bekommt `output.json` mit den gefundenen EPD-UUIDs (`id`) und `id_confidence`.

Ergebnis: pro Schicht bis zu 10 nach Confidence sortierte EPD-Vorschläge. Der Mensch wählt im
LCA-Tool final aus (semi-automatischer Workflow).

---

## Die 5-Stage-Pipeline

Jeder Lauf durchläuft fünf Stages. Jede ist über `.env` schaltbar; in `config/settings.py`
entspricht jeder Stage genau eine Config-Klasse.

| Stage | Modul | Aufgabe |
|---|---|---|
| **1 — Kontext-Extraktion** | `main.py` | Liest `NAME` und `MATERIAL` je Gruppe; entscheidet, welches Feld führend ist (`EPD_PREFER_NAME_FIELD`). |
| **2 — Material-Code-Parsing** | `utils/asphalt_glossar.py` | Parst deutsche Asphalt-Codes (`AC 16 B S`) in Typ, Schicht, Beanspruchung. |
| **3 — EPD-Vorfilterung** | `matching/epd_filter.py` (`EPDFilter`) | Reduziert den Katalog (10 000+ EPDs) auf relevante Kandidaten — der zentrale Kostenhebel. |
| **4 — LLM-Matching** | `matching/azure_matcher.py` + `matching/prompt_builder.py` | Schickt einen strukturierten Prompt an Azure OpenAI; bekommt JSON mit `id`, `confidence`, `begruendung`. |
| **5 — Confidence-Validierung** | `matching/epd_filter.py` (`ConfidenceValidator`) | Regelbasierte Nachkorrektur: kappt Scores bei Ausschluss-Begriffen, Typ-Mismatch, fehlender Schicht. |

> **Hinweis zur Studie:** Im Paper werden nur drei Stages als binäre Variablen abladiert
> (siehe [Ablations-Schalter](#ablations-schalter)). Stage 2 (Glossar) und Stage 5
> (Confidence-Cap) bleiben dabei **konstant**.

---

## Setup

1. **`.env` anlegen** — die Vorlage `readme` (ohne Endung) nach `.env` kopieren und ausfüllen:

   ```
   AZURE_OPENAI_API_KEY=...
   ENDPOINT_URL=...
   # nur für EPD_DATA_SOURCE=online:
   ONLINE_EPD_API_BASE_URL=...
   ONLINE_EPD_API_USERNAME=...
   ONLINE_EPD_API_PASSWORT=...
   ```

2. **Abhängigkeiten installieren:**

   ```
   pip install openai python-dotenv requests
   ```

3. **(Empfohlen) Lokale ÖKOBAUDAT-Kopie ziehen** für reproduzierbare Läufe:

   ```
   python download_oekobaudat.py
   ```
   Erzeugt die SQLite-DB unter `LOCAL_DB_PATH` (Standard `data/oekobaudat.db`). Danach
   `EPD_DATA_SOURCE=local` setzen.

---

## Ausführen

**Haupt-Matcher** — verarbeitet einen Ordner mit `input/input.json`, schreibt `output/output.json`:

```
python main.py <id_ordner>
# z.B.
python main.py TestInput/id_aufruf_benutzer
```

Flags:

| Flag | Wirkung |
|---|---|
| `--input-file <name>` | Name der Eingabedatei (Standard `input.json`) |
| `--output-file <name>` | Name der Ausgabedatei (Standard `output.json`) |
| `--no-batch` | Einzelmodus: ein LLM-Call pro Schicht statt einem für alle |

**Module isoliert testen** (jedes Modul hat einen eigenen Testblock):

```
python matching/epd_filter.py        # Filter + Confidence-Validierung
python utils/asphalt_glossar.py      # Material-Parsing
python datasources/local_store.py    # lokale DB
python datasources/oekobaudat_client.py   # Live-API (gemockt)
```

---

## Ein-/Ausgabe-Format

**Eingabe** (`input/input.json`):

```json
{
  "Gruppen": [
    { "NAME": "Deckschicht", "MATERIAL": "AC 11 D S", "Volumen": 42.38, "GUID": ["2O2Fr$..."] }
  ]
}
```

| Feld | Bedeutung |
|---|---|
| `NAME` | Funktionale Schicht-Bezeichnung (Deckschicht, Binderschicht, Tragschicht, Schottertragschicht, Frostschutzschicht) |
| `MATERIAL` | Material-Spezifikation, z.B. `AC 11 D S` |
| `GUID` | Liste der IFC-Element-IDs der Gruppe |
| `Volumen` | Aggregiertes Volumen (Bezugsgröße fürs LCA-Tool) |

**Ausgabe** — dasselbe Schema, ergänzt pro Gruppe um:

| Feld | Bedeutung |
|---|---|
| `id` | Liste der gematchten EPD-UUIDs (Top-Treffer zuerst) |
| `id_confidence` | Map `uuid → Confidence (0–100)` |

---

## Datenquellen

Über `EPD_DATA_SOURCE` wählbar (`config/settings.py` → `DataSourceConfig`, Naht in
`datasources/factory.py`, siehe `docs/adr/0001-...`):

| Wert | Quelle | Wann |
|---|---|---|
| `online` | Alte JWT-gesicherte REST-API | Legacy; aktuell tot, braucht gültige Zugangsdaten |
| `oekobaudat` | Live über soda4LCA-REST-API | Stichproben; zieht ~5720 Sätze pro Lauf frisch |
| `local` | Heruntergeladene SQLite-Kopie | **Empfohlen** für wiederholte Versuche; enthält auch eigene `custom`-Einträge |

Alle drei erfüllen denselben internen **EPD-Vertrag** (`list_epds` / `get_epd_details` /
`count_epds`), sodass Filter, Prompt und Matcher quellunabhängig bleiben.

---

## Einstellungen

Alle Einstellungen kommen aus Umgebungsvariablen (`.env`), gelesen in `config/settings.py`. Beim
Import wird eine Konfigurations-Zusammenfassung gedruckt (gewollt).

### Azure OpenAI (Stage 4)

| Variable | Standard | Bedeutung |
|---|---|---|
| `AZURE_OPENAI_API_KEY` | — | API-Schlüssel (Pflicht) |
| `ENDPOINT_URL` | — | Azure-Endpoint (Pflicht) |
| `AZURE_DEPLOYMENT` | `gpt-4o-mini` | Deployment-/Modellname |
| `AZURE_API_VERSION` | `2024-12-01-preview` | API-Version |
| `AZURE_TIMEOUT` | `240.0` | Timeout in Sekunden |
| `AZURE_MAX_RETRIES` | `3` | Wiederholungen bei Fehlern |

### Datenquelle

| Variable | Standard | Bedeutung |
|---|---|---|
| `EPD_DATA_SOURCE` | `online` | `online` \| `oekobaudat` \| `local` |
| `LOCAL_DB_PATH` | `data/oekobaudat.db` | Pfad der lokalen SQLite-DB |
| `OEKOBAUDAT_BASE_URL` | `https://www.oekobaudat.de/OEKOBAU.DAT/resource` | soda4LCA-Basis-URL |
| `OEKOBAUDAT_LANG` | `de` | Sprache der Detailtexte |
| `OEKOBAUDAT_PAGE_SIZE` | `500` | Seitengröße beim Paging |
| `OEKOBAUDAT_CLASSIFICATION` | *(leer)* | Optionaler serverseitiger Klassifikations-Filter (`classId`); leer = ganzer Katalog |
| `OEKOBAUDAT_CLASS_SYSTEM` | `oekobau.dat` | Klassifikationssystem für obigen Filter |
| `ONLINE_EPD_API_BASE_URL` / `_USERNAME` / `_PASSWORT` | — | Zugangsdaten für `online` |

### Stage 1 — Kontext

| Variable | Standard | Bedeutung |
|---|---|---|
| `EPD_PREFER_NAME_FIELD` | `true` | **NamePref**-Schalter: `NAME` (Schichtfunktion) führend statt `MATERIAL` |
| `EPD_EXTRACT_VOLUME` | `true` | Volumen für LCA extrahieren |

### Stage 2 — Glossar / Parsing

| Variable | Standard | Bedeutung |
|---|---|---|
| `EPD_USE_GLOSSAR` | `true` | Intelligentes TL-Asphalt-StB-Parsing aktivieren |
| `EPD_GLOSSAR_DEBUG` | `false` | Parsing-Ergebnisse mitloggen |

### Stage 3 — Vorfilterung

| Variable | Standard | Bedeutung |
|---|---|---|
| `EPD_USE_GLOSSAR_FILTER` | `true` | **Filter**-Schalter: Katalog vor dem LLM reduzieren |
| `EPD_USE_FILTER_LABELS` | `false` | Legacy: einfacher Label-Filter |
| `EPD_FILTER_LABELS` | *(leer)* | Komma-Liste für Label-Filter |

### Stage 4 — LLM-Matching

| Variable | Standard | Bedeutung |
|---|---|---|
| `EPD_USE_BATCH_MODE` | `true` | **Batch**-Schalter: alle Schichten in einem LLM-Call (günstiger, evtl. ungenauer) |
| `PROMPT_MAX_EPD` | `500` | Sicherheits-Obergrenze für EPDs im Prompt (nur Token-Limit-Schutz; Vorfilter sortiert primär-zuerst) |
| `EPD_MAX_RESULTS` | `10` | Max. Treffer pro Material |
| `EPD_USE_DETAIL_MATCHING` | `false` | Detailfelder (`technischeBeschreibung` etc.) mitladen — nur mit `local` sinnvoll |
| `EPD_MATCHING_COLUMNS` | `name,technischeBeschreibung,anmerkungen` | Spalten im Detail-Modus |
| `EPD_PARALLEL_WORKERS` | `10` | Parallele Calls beim Detail-Laden |

### Stage 5 — Confidence-Validierung

| Variable | Standard | Bedeutung |
|---|---|---|
| `EPD_USE_CONFIDENCE_VALIDATION` | `true` | Regelbasierte Nachkorrektur aktivieren |
| `EPD_MIN_CONFIDENCE` | `25` | Treffer darunter werden verworfen |
| `EPD_MAX_CONFIDENCE_EXCLUDED` | `20` | Cap für Treffer mit Ausschluss-Begriff |

### Ablations-Schalter

Die Studie variiert genau **drei** binäre Schalter; daraus ergeben sich 8 Konfigurationen (P1–P8):

| Schalter | Variable |
|---|---|
| **Batch** | `EPD_USE_BATCH_MODE` |
| **Filter** | `EPD_USE_GLOSSAR_FILTER` |
| **NamePref** | `EPD_PREFER_NAME_FIELD` |

| ID | Batch | Filter | NamePref | | ID | Batch | Filter | NamePref |
|---|---|---|---|---|---|---|---|---|
| P1 | – | – | – | | P5 | ✓ | – | ✓ |
| P2 | ✓ | – | – | | P6 | – | ✓ | ✓ |
| P3 | – | ✓ | – | | P7 | ✓ | ✓ | – |
| P4 | – | – | ✓ | | P8 | ✓ | ✓ | ✓ |

`EPD_USE_GLOSSAR` (Stage 2) und `EPD_USE_CONFIDENCE_VALIDATION` (Stage 5) bleiben in allen acht
Konfigurationen konstant aktiv.

---

## Projektstruktur

```
main.py                     Einstieg, Stage 1, Batch-/Einzelmodus
config/settings.py          Zentrale Config (eine Klasse pro Stage)
utils/
  asphalt_glossar.py        Stage 2: Material-Parsing + TL-Asphalt-StB-Vokabular
  cost_tracker.py           Token-/Kostenzählung pro Lauf
  file_handler.py           JSON laden/speichern
matching/
  epd_filter.py             Stage 3 (EPDFilter) + Stage 5 (ConfidenceValidator)
  azure_matcher.py          Orchestriert die Pipeline, Azure-Calls
  prompt_builder.py         Baut die LLM-Prompts (kompakt / Detail)
datasources/
  base.py                   EPD-Vertrag (Protocol)
  factory.py                Wählt Quelle nach EPD_DATA_SOURCE
  local_store.py            SQLite-Quelle
  oekobaudat_client.py      Live soda4LCA-Quelle
  oekobaudat_mapping.py     Mapping soda4LCA → EPD-Vertrag
  sqlite_schema.py          DB-Schema
api/                        Legacy Online-API (auth + client)
download_oekobaudat.py      Befüllt die lokale SQLite-DB
docs/
  adr/                      Architektur-Entscheidungen
  plans/                    Implementierungspläne
CONTEXT.md                  Domänen-Glossar (verbindliches Vokabular)
```

Domänen-Vokabular und Architektur-Entscheidungen: siehe `CONTEXT.md` und `docs/adr/`.
