# EC3 EPD-Matcher

Ordnet Bau-Materialschichten (v.a. deutscher Straßenbau) den passenden EPD-Datensätzen
zu — über eine 5-stufige Pipeline aus Glossar-Vorfilterung und LLM-Matching.

## Language

### Datenquellen

**EPD-Datenquelle**:
Die austauschbare Herkunft der EPD-Datensätze, gewählt über `EPD_DATA_SOURCE`. Es gibt
genau vier: `online`, `oekobaudat`, `local`, `local-custom`. `local` und `local-custom`
teilen denselben Code-Pfad (`LocalEPDStore`) und unterscheiden sich nur in der DB-Datei.
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
Die **reine** heruntergeladene Kopie der Ökobaudat als SQLite-DB (`data/oekobaudat.db`),
ausschließlich `source='oekobaudat'`. Empfohlener Modus für reproduzierbare Experimente; die
unveränderte Datengrundlage der Hauptablation.
_Avoid_: Cache, Offline-DB, Snapshot

**local-custom**:
Eine **angereicherte Kopie** der `local`-DB (`data/oekobaudat_custom.db`), die zusätzlich die
[[custom-Eintrag]]e aus dem `custom_entries_config.json` enthält. Per `EPD_DATA_SOURCE=local-custom`
gewählt; macht im Run-Provenance explizit, dass gegen den angereicherten Korpus gematcht wurde. Die
`local`-DB bleibt davon unberührt.
_Avoid_: Custom-DB, modifizierte DB, enriched-DB

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
Ein selbst angelegter EPD-Datensatz mit `source='custom'`, der **nur** in der
[[local-custom]]-DB lebt (nie in `local`). Erfüllt denselben [[EPD-Vertrag]], wird ohne
Sonderbehandlung mitgelesen. Quelle der Wahrheit ist das `custom_entries_config.json`; die DB ist
ein daraus abgeleitetes, neu-baubares Artefakt.
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

### Studie — Artefakte

Alle Studie-Artefakte liegen unter `docs/studie/`:

- **`docs/studie/2026_EC3_LLM_Based_EPD_Matching.pdf`** — Ersteinreichung. Paper zur
  EC³ 2026 (Corfu, Greece, July 12–15 2026). Beschreibt Pipeline P1–P8, Accuracy-Heatmap
  und Cost-Efficiency-Ranking. Titel: „Implementation of an LLM-Based Method for EPD Matching
  in BIM Workflows". Funding: BMV mFUND SusInfra.
- **`docs/studie/EC3_Comments.docx`** — Gutachter-Kommentare (2 Reviewer) zur Ersteinreichung.
- **`docs/studie/EPD_Ablation_20260123_170211.xlsx`** — Excel-Auswertung der Benchmark-Runs
  (Sheets: Ablation-Study, Ground-Truth, Accuracy-pro-Schicht, Benchmark-Summary u.a.).

Das Benchmark-Skript der ersten Studie liegt unter `benchmark/archiv/benchmark_alltests.py`.

### Studie v1 — Ergebnisse (Ersteinreichung)

**Testaufbau**: 1 IFC-Modell, 1 standardisierter 5-Schicht-Straßenaufbau, 5 Repetitionen pro
Konfig×Modell-Kombination, 4 Modelle (gpt-4o-mini, gpt-5-nano, gpt-5-chat, gpt-5.2-chat).
**Evaluated Layers**: 3 von 5 (2 Schichten ohne passendes ÖKOBAUDAT-EPD ausgeschlossen).
**Accuracy-Metrik**: Top-1-Match = Ground-Truth-UUID → 1 Punkt; sonst 0.

**Accuracy-Heatmap** (Mittelwert über 5 Runs, in %):

| Config | gpt-4o-mini | gpt-5-nano | gpt-5-chat | gpt-5.2-chat |
|--------|-------------|------------|------------|--------------|
| P1     | 100         | 100        | 100        | 100          |
| P2     | 100         | 86.7       | 100        | 100          |
| P3     | 100         | 80         | 100        | 100          |
| P4     | 86.7        | 60         | 66.7       | 66.7         |
| P5     | 73.3        | 53.3       | 66.7       | 66.7         |
| P6     | 73.3        | 66.7       | 73.3       | 93.3         |
| P7     | 80          | 86.7       | 100        | 93.3         |
| P8     | 66.7        | 66.7       | 66.7       | 53.3         |

**Bestes Cost-Efficiency-Ergebnis**: gpt-4o-mini + P3 (Filter only) — 100% Accuracy bei
geringstem Kosten-pro-Accuracy-Punkt-Score (0,014). P1 mit gpt-4o-mini: gleiche Accuracy,
aber 12× teurer.

**Accuracy aggregiert über alle Modelle** (Accuracy-pro-Schicht-Sheet):
P1 (Baseline) 100% → P2 96,7% → P3 95% → P7 90% → P6 76,7% → P4 70% → P5 65% → P8 63,3%.
Kosteneinsparung vs. P1: P3 −80%, P7 −89%, P8 −88%.

### Studie v1 — Reviewer-Kritik (für v2 maßgeblich)

**Reviewer 1 — zentrale Punkte:**
1. Einzelner Testfall reicht nicht. 1 Pavement + 5 Schichten ist zu schmal; P1 mit 100%
   über alle Modelle deutet auf trivialen Test hin.
2. Der eigentliche Beitrag (Matching Tool) ist am wenigsten erklärt — kein Architekturdiagramm,
   kein Interface-Schema.
3. Umgang mit fehlenden EPDs nicht adressiert (Sparse-EPD-Problem).
4. IFC-Datenqualität für Straßen (im Vergleich zu Gebäuden) nicht diskutiert.
5. Neuheitsabgrenzung zu Forth et al. (2023), Hermann et al. (2024), Petrosa et al. (2025)
   fehlt; Unterschiede wirken implementierungstechnisch, nicht methodisch.

**Reviewer 2 — zentrale Punkte:**
1. Einzelner Testfall + keine Detailangaben zu Fallstudien.
2. Cost-Efficiency-Score fragwürdig: weniger genaue Ergebnisse sind nicht sinnvoll, auch wenn
   sie günstig sind. Begründung für die Metrik fehlt.
3. Prompt-Design nicht erläutert — Beispiel fehlt.
4. Table 1 (Ablations-Konfigurationen) nicht ausreichend eingeführt: Was bedeutet „Baseline"?
   Warum diese 8 Kombinationen?
5. Token-Kosten-Argument gilt nur für kommerzielle LLMs — Open-Source-Alternativen fehlen.
6. Fehlende Referenzen: Hofmeyer et al. 2023, Chen et al. 2024.

**Kernproblem für v2**: Beide Reviewer beanstanden primär den **single-test-case**. Die neue
Studie muss zwingend mehrere, diverse Eingabe-Inputs (verschiedene Schichtzusammensetzungen,
abweichende Namenskonventionen) verwenden. Außerdem muss die Cost-Efficiency-Metrik neu
begründet oder ersetzt werden.
