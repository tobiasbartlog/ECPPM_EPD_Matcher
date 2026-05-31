# EC3 EPD-Matcher

Ordnet Bau-Materialschichten (v.a. deutscher Straßenbau) den passenden EPD-Datensätzen
zu — über eine 5-stufige Pipeline aus Glossar-Vorfilterung und LLM-Matching.

## Language

### Datenquellen

**EPD-Datenquelle**:
Die austauschbare Herkunft der EPD-Datensätze, gewählt über `EPD_DATA_SOURCE`. Es gibt
genau drei: `online`, `oekobaudat`, `local`.
_Avoid_: API, Backend, Provider

**online**:
Die alte, JWT-gesicherte REST-API des EPD-Dienstleisters. Aktuell tot — bleibt als Modus
erhalten, schlägt aber ohne gültige Zugangsdaten fehl.
_Avoid_: Legacy-API, alte API

**oekobaudat**:
Die Ökobaudat als **Live**-Quelle über die öffentliche soda4LCA-REST-API. Zieht den Katalog
pro Lauf frisch; für wiederholte Versuche ist `local` vorzuziehen.
_Avoid_: soda4LCA, Live-API, ÖBD

**local**:
Eine heruntergeladene Kopie der Ökobaudat als SQLite-DB. Empfohlener Modus für Experimente;
enthält neben heruntergeladenen Datensätzen auch eigene `custom`-Einträge.
_Avoid_: Cache, Offline-DB, Snapshot

### Datensätze

**EPD-Vertrag**:
Das interne, normalisierte EPD-Dict, an dem die gesamte Pipeline hängt. Pflichtfelder
`id`, `name`, `klassifizierung`; Detailfelder (z.B. `technischeBeschreibung`) nur bei
aktivem Detail-Matching. Jede Datenquelle erfüllt genau diesen Vertrag.
_Avoid_: EPD-Objekt, Record, Schema, DTO

**Klassifizierung**:
Der deutsche Klassifikationspfad eines Datensatzes als ein String, z.B.
`"Mineralische Baustoffe / Asphalt / Tragschichten"`. Zusammen mit `name` die einzige
Grundlage des Glossar-Filters — muss daher deutsche Begriffe enthalten.
_Avoid_: Kategorie, classific, classification_path, Pfad

**custom-Eintrag**:
Ein selbst angelegter EPD-Datensatz in der lokalen DB mit `source='custom'`. Wird direkt
per SQL eingefügt und ohne Sonderbehandlung mitgelesen.
_Avoid_: eigener Datensatz, Testdatensatz, manueller Eintrag

**Listen-Ebene / Detail-Ebene**:
Listen-Ebene = die Basisfelder, die der Ökobaudat-Listen-Endpunkt für alle Datensätze auf
einmal liefert (deckt den Pflicht-Vertrag). Detail-Ebene = die langen deutschen ILCD-Texte,
die pro `uuid` einzeln nachgeladen werden (nur bei Detail-Matching).
_Avoid_: Basis/Voll, kurz/lang

### Pipeline

**Glossar-Filter**:
Stage 3 der Pipeline. Reduziert den EPD-Katalog auf relevante Kandidaten, indem er deutsche
Substrings (`asphalt`, `trag`, `deck`, `binder`, …) in `name + klassifizierung` sucht —
bevor an das LLM geschickt wird. Datenquellen-unabhängig.
_Avoid_: Vorfilter, EPDFilter, Pre-Filtering
