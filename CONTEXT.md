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
Stage 3 der Pipeline. Reduziert den EPD-Katalog auf relevante Kandidaten — bevor an das LLM
geschickt wird. Datenquellen-unabhängig. Dünner Aufrufer von [[matching-rules]].
Asymmetrische Filterlogik: **Inklusion** (Suchbegriffe, Schicht-Treffer) gegen `name` —
verhindert Treffer auf breite Oberbegriffe in `klassifizierung`; **Exklusion** (Ausschluss-
und Mismatch-Begriffe) gegen `name + klassifizierung`. Ausnahme: `ist_asphalt`-Erkennung
prüft `name + klassifizierung`, da `"Asphalt / ..."` in der Klassifizierung zuverlässig und
spezifisch ist (kein Explosionsrisiko wie generische Kategorie-Suchbegriffe).
_Avoid_: Vorfilter, EPDFilter, Pre-Filtering

**matching_rules**:
Das tiefe Modul mit den geteilten Fakten darüber, ob ein EPD-Kandidat zu einem Material passt.
Einzige Quelle für Ausschluss-, Kategorie- und Mismatch-Wissen (löst die frühere Dreifach-
Duplizierung über `AUSSCHLUSS_BEGRIFFE`, `MATERIAL_KATEGORIEN` und `MATERIAL_MISMATCHES` ab).
Stellt `bewerte_kandidat(material, epd) -> Bewertung` bereit; importiert den Stage-2-Parser aus
`asphalt_glossar`, verschiebt ihn aber nicht. Stage 3 (Glossar-Filter) und Stage 5
(Confidence-Validierung) sind dünne Aufrufer und bleiben getrennte Policies.
_Avoid_: Materialkunde, Validator, Scoring-Engine

**Bewertung**:
Das Fakten-Objekt aus `bewerte_kandidat` — die Tatsachen über ein (Material, EPD)-Paar
(`ist_asphalt`, `ausgeschlossen`, `schicht_passt`, `kategorie_konflikt`), nicht die Policy.
Stage 3 liest sie als Tor (primär/sekundär/raus), Stage 5 als Confidence-Cap. Die beiden
Policies dürfen bewusst verschieden bleiben.
_Avoid_: Score, Verdikt, Match-Result

**5-Stage-Pipeline**:
Die feste Reihenfolge jedes Laufs: (1) Kontext-Extraktion, (2) Material-Code-Parsing (Glossar),
(3) EPD-Vorfilterung, (4) LLM-Matching, (5) Ergebnis-Aggregation + Confidence-Validierung. Die
Stage-Grenzen sind die Struktur des Papers — eine Config-Klasse in `settings.py` pro Stage. Nicht
verwischen.
_Avoid_: Schritte, Phasen, Module (für die Stages)

**Confidence-Cap**:
Stage 5. Regelbasierte Nachkorrektur der LLM-Confidence: kappt auf `MAX_CONFIDENCE_EXCLUDED` bei
Ausschluss/Kategorie-Konflikt, auf 60 bei fehlender Schicht. Bewusst **konstant** in allen
Konfigurationen (kein Ablations-Schalter) — im Paper als Nachkorrektur dokumentiert, nicht als
Variable. Liest [[Bewertung]].
_Avoid_: Validierung (allein), Scoring, Re-Ranking

### Workflow & Systeme

**CDE**:
Common Data Environment. Liefert die IFC-abgeleiteten Eingaben (Schicht-Name, Material, GUIDs,
Volumen) als `input.json` pro Task-Ordner und nimmt die angereicherten Ergebnisse zurück. Das
Matching-Tool ist der zentrale Knoten zwischen CDE, EPD-Datenquelle und LCA-Tool.
_Avoid_: BIM-Tool, Frontend, Plattform

**LCA-Tool**:
Nachgelagertes Ökobilanz-Werkzeug. Bekommt die Schicht-Info angereichert um EPD-UUIDs (`id`) und
`id_confidence`; nutzt `Volumen` als Bezugsgröße für die Hochrechnung.
_Avoid_: Ökobilanzierer, Impact-Tool

**JSON-Vertrag**:
Das gemeinsame Eingabe-/Ausgabe-Schema (`NAME`, `MATERIAL`, `GUID`, `Volumen` je `Gruppe`). Ein-
und Ausgabe nutzen dasselbe Schema; die Ausgabe ergänzt `id` und `id_confidence`. Nicht zu
verwechseln mit dem internen [[EPD-Vertrag]].
_Avoid_: Input-Format, Payload, DTO

**Schicht-Taxonomie**:
Die fünf normierten Schicht-Namen (RStO-orientiert): Deckschicht, Binderschicht, Tragschicht,
Schottertragschicht, Frostschutzschicht. Im `NAME`-Feld geführt; korrespondiert direkt mit
EPD-Klassifizierungen und treibt die [[matching-rules]]-Schicht-Prüfung.
_Avoid_: Layer-Typen, Aufbau

### Experiment

**Ablations-Schalter**:
Die drei binären Variablen der Studie: **Batch** (`EPD_USE_BATCH_MODE`), **Filter**
(`EPD_USE_GLOSSAR_FILTER`), **NamePref** (`EPD_PREFER_NAME_FIELD`). Ergeben 2×2×2 = 8
Konfigurationen P1–P8. **Glossar** (Stage 2) und **Confidence-Cap** (Stage 5) sind bewusst
*nicht* abladiert — sie bleiben konstant. Jeder Refactor muss diese drei Schalter einzeln
schaltbar lassen.
_Avoid_: Flags, Optionen, Parameter (für die drei Studien-Variablen)

**Stage-2-Vorbehalt**:
Material-Code-Parsing (Glossar) ist beim aktuellen ÖKOBAUDAT-Bestand „in den meisten Fällen
obsolet&ldquo;, weil kaum produktspezifische Infrastruktur-EPDs existieren und meist nur generische
Datensätze matchen. Der Parser bleibt erhalten (er speist das `schicht_muss`-Signal des Filters),
sein Mehrwert wächst aber erst mit der Datenbankabdeckung.
_Avoid_: (keine)

**Ground Truth**:
Der pro Schicht manuell in der ÖKOBAUDAT bestimmte „richtige&ldquo; EPD-Datensatz, gegen den die
Accuracy gemessen wird. Schichten ohne passenden EPD werden aus der Bewertung ausgeschlossen.
_Avoid_: Soll-Wert, Referenz, Gold-Standard
