# Paper Design Document — EC³ 2026 Revision

Dieses Dokument hält alle paper-relevanten Designentscheidungen fest, die im Verlauf des
Projekts getroffen werden. Es wird laufend aktualisiert. Ziel: Wenn das Paper geschrieben
wird, findet sich hier eine nachvollziehbare Dokumentation der Entscheidungen, die direkt
in den Methodik- und Diskussionsteil einfließen kann.

---

## Kontext

**Paper**: „Implementation of an LLM-Based Method for EPD Matching in BIM Workflows"
**Konferenz**: EC³ 2026, Corfu, Greece, 12.–15. Juli 2026
**Funding**: BMV mFUND SusInfra
**Status**: Resubmission nach Ablehnung durch 2 Reviewer

---

## 1. Studiendesign

### 1.1 Testfälle

**Entscheidung**: 3 synthetische Input-JSONs statt 1.

**Begründung**: Reviewer 1+2 beanstandeten, dass ein einziger standardisierter 5-Schicht-Aufbau
als Testfall nicht ausreicht. P1 (Baseline) erreichte 100% Accuracy über alle 4 Modelle, was
auf einen trivialen Testfall hindeutet. Mit 3 strukturell unterschiedlichen Inputs kann im
Paper von „mehreren diversen Szenarien" gesprochen werden.

**Struktur**: Alle 3 Inputs haben dieselben 5 Schichten (NAME-Feld identisch, manuell gesetzt):
- Deckschicht
- Binderschicht
- Bituminöse Tragschicht
- Nicht bituminöse Tragschicht
- Frostschutzschicht

Die Schicht-Namen orientieren sich an RStO-Nomenklatur und dem vorliegenden Schichttaxonomie-
Dokument (Asphaltmischgutarten mit Mindest- und Maximal-Größtkorn). NAME wird immer manuell
zugewiesen — es gibt keine Variante mit uninformativen NAME-Werten.

**Variation**: Ausschließlich MATERIAL-Feld unterscheidet die 3 Inputs.

- **Input A (Standard)**: Replikation des v1-Aufbaus mit aktualisierten Layer-Namen
- **Input B**: Andere Asphalttypen/Mischgutarten (z.B. Splittmastixasphalt, Gussasphalt)
- **Input C**: Mindestens eine nicht-bituminöse Schicht (z.B. hydraulisch gebundene Tragschicht,
  Gesteinskörnungsgemisch) — stresst den Glossar-Filter außerhalb des Asphalt-Bereichs

*Material-Werte noch offen — werden nach ÖKOBAUDAT-Lookup festgelegt.*

### 1.2 Ablations-Konfigurationen

**Entscheidung**: P1–P8 unverändert aus v1 (vollfaktorielle 2×2×2-Ablation).

| ID | Name | Batch | Filter | NamePref |
|----|------|-------|--------|----------|
| P1 | Baseline | — | — | — |
| P2 | Batch | ✓ | — | — |
| P3 | Filter | — | ✓ | — |
| P4 | NamePref | — | — | ✓ |
| P5 | BatchName | ✓ | — | ✓ |
| P6 | FilterName | — | ✓ | ✓ |
| P7 | BatchFilter | ✓ | ✓ | — |
| P8 | All | ✓ | ✓ | ✓ |

**Begründung**: Reviewer 2 fragte, warum genau diese Kombinationen. Antwort: vollständige
Faktorielle über 3 binäre Variablen deckt alle Interaktionseffekte ab. Diese Begründung fehlt
in v1 und muss im Paper explizit gemacht werden (Referenz: Fostiropoulos & Itti 2023).

**Konstante Faktoren** (nicht abladiert, Begründung im Paper notwendig):
- Stage 2 (Glossar-Parsing): bleibt aktiv, aber sein Beitrag ist gering da ÖKOBAUDAT kaum
  produktspezifische Infrastruktur-EPDs hat → „Stage-2-Vorbehalt" im Paper dokumentieren
- Stage 5 (Confidence-Cap): bleibt aktiv als post-processing Konstante

### 1.3 Modelle

**Entscheidung**: Dieselben 4 Azure-Deployments wie v1.
- gpt-4o-mini
- gpt-5-nano
- gpt-5-chat
- gpt-5.2-chat

**Begründung**: Vergleichbarkeit mit v1. Preisdatum wird im Paper explizit genannt (wie in v1).

**Offene Reviewer-Kritik**: Reviewer 2 bemängelte, dass das Token-Kosten-Argument nur für
kommerzielle LLMs gilt, nicht für Open-Source-Alternativen. → Im Paper als Limitation nennen:
„This study uses commercial Azure OpenAI deployments; open-source alternatives (e.g., Llama 3,
Mistral) were not evaluated and may offer different cost-accuracy tradeoffs."

### 1.4 Repetitionen

**Entscheidung**: 5 Repetitionen pro Config×Modell×Input.

**Begründung**: LLM-Stochastizität macht mehrere Runs notwendig. Mit 3 Inputs ergibt sich
pro Config×Modell-Kombination 5 Reps × 3 Inputs = 15 Beobachtungen — methodisch stärker
als 5 Reps × 1 Input in v1. Gesamtaufwand: 480 Runs.

**Verbindung zum Paper**: Diese Begründung (Stochastizität → mehrere Reps) war in v1 bereits
enthalten und soll in v2 beibehalten werden.

### 1.5 Datenquelle

**Entscheidung**: `EPD_DATA_SOURCE=local` (SQLite-Snapshot der ÖKOBAUDAT).

**Begründung**: Reproduzierbarkeit. Alle 480 Runs laufen gegen denselben Datenbankstand.
Snapshot-Datum wird im Paper dokumentiert.

---

## 2. Ground Truth

### 2.1 Definition

**Entscheidung**: Top-1-Accuracy gegen manuell bestimmte Ground-Truth-UUID pro Schicht und Input.

**Prozess**: Nach den Benchmark-Runs erzeugt das Skript eine `ground_truth_template.json` pro
Input-Ordner, vorausgefüllt mit dem häufigsten Top-1-Match und EPD-Namen. Der Forscher
überprüft/korrigiert und speichert als `ground_truth.json`.

**Wichtig für das Paper**: Ground Truth basiert auf manuellem ÖKOBAUDAT-Lookup. Es wird
explizit dokumentiert, dass mehrere EPDs akzeptable Treffer sein könnten — dies ist eine
Limitation (wie in v1 bereits erwähnt). Future work: multiple acceptable labels with weights
oder Expert-Consensus-Ansatz (wie von Reviewer 1 impliziert).

### 2.2 Ausschluss-Regel

**Entscheidung**: Schichten mit `ground_truth = null` werden aus Accuracy-Berechnung
ausgeschlossen.

**Begründung**: Für die „Nicht bituminöse Tragschicht" und ggf. weitere Schichten existiert
möglicherweise kein adäquates EPD in ÖKOBAUDAT. Diese Schichten können nicht bewertet werden.
Anzahl der bewerteten Schichten wird im Paper explizit angegeben (wie in v1: „3 von 5
Schichten bewertet").

---

## 3. Metriken

### 3.1 Primärmetrik: Top-1 Accuracy

**Definition**: Anteil der Runs, bei denen der erste zurückgegebene Match die Ground-Truth-UUID
trifft. Berechnet über bewertete Schichten (Ground Truth ≠ null), aggregiert über 5 Reps
und 3 Inputs.

**Begründung**: Direkte Messung der Matching-Qualität. Einfach zu verstehen und zu kommunizieren.

### 3.2 Sekundärmetrik: Cost-at-Threshold

**Definition**: Unter allen Konfigurationen, die mindestens die P1-Accuracy (Baseline) erreichen,
werden die Kosten verglichen. P1-Threshold wird dynamisch aus den tatsächlichen P1-Runs
berechnet (nicht als fixer Prozentwert).

**Begründung**: Adressiert Reviewer 2's Kritik am alten Cost-Efficiency-Score, der günstige
aber ungenaue Konfigurationen bevorzugte. Der neue Ansatz stellt sicher, dass nur Konfigurationen
mit ausreichender Qualität verglichen werden.

**Paper-Formulierung**: „Among configurations achieving at least baseline accuracy, P3
reduces cost by X% compared to P1."

### 3.3 Abgelehnte Metrik: Cost per Accuracy Point

Der in v1 verwendete Score `Cost / Accuracy [%]` wurde von Reviewer 2 als „not plausible"
abgelehnt. Er wird in v2 nicht verwendet.

---

## 4. Systemarchitektur — Paper-relevante Entscheidungen

### 4.1 Drei-Skript-Architektur

**Entscheidung**: Messung, Analyse und Custom-Entries-Experiment sind getrennte Skripte.

| Skript | Aufgabe | Output |
|--------|---------|--------|
| `benchmark/ablation_benchmark.py` | 480 Runs ausführen, Rohdaten sammeln | `benchmark_runs.json`, GT-Vorlagen, Rohdaten-HTML/Excel |
| `benchmark/ablation_analysis.py` | Accuracy berechnen, Paper-Charts | `ablation_analysis.html`, `ablation_analysis.xlsx` |
| `benchmark/custom_entries_experiment.py` | Sparse-EPD-Sensitivität messen | `custom_entries_report.html` |

**Begründung für das Paper**: Trennung von Messung und Auswertung ermöglicht nachträgliche
Ground-Truth-Korrekturen ohne erneute LLM-Runs. Das Custom-Entries-Skript läuft gegen eine
DB-Kopie — die Original-DB bleibt unverändert und alle Läufe bleiben reproduzierbar.

### 4.2 Prompt-Design (offen — für Reviewer 2 dokumentieren)

Reviewer 2 kritisierte: „How was the prompt designed? An example would support the reader."

→ **TODO**: Sobald finale Prompt-Struktur feststeht, hier dokumentieren:
- Welche Felder werden dem LLM übergeben (name, technischeBeschreibung, anmerkungen)?
- Wie ist der System-Prompt aufgebaut (Matching-Regeln, Output-Format)?
- Wie wird Batch-Mode vs. Single-Call im Prompt unterschieden?
- Ein Beispiel-Prompt-Ausschnitt für das Paper vorbereiten.

### 4.3 Begründung der Kombinationsauswahl (für Reviewer 2 dokumentieren)

Reviewer 2 fragte: „How were the combinations decided? What does baseline mean?"

→ **Antwort für Paper**:
- Vollständige Faktorielle: 3 binäre Faktoren → 2³ = 8 Kombinationen. Keine Teilmenge,
  da Interaktionseffekte (z.B. Batch+Filter zusammen) nur so sichtbar werden.
- P1 = Baseline: alle drei Optimierungen deaktiviert. Maximale Token-Nutzung, keine
  Vorverarbeitung. Dient als obere Accuracy-Schranke und Kosten-Referenz.

---

## 5. Zusatzexperiment: Custom Entries

**Entscheidung**: Kleines Zusatzexperiment (~20 Runs) mit modifizierter lokaler DB, um zu
zeigen, dass Accuracy mit besserer ÖKOBAUDAT-Abdeckung steigt.

**Methode**: Beste Konfiguration (gpt-4o-mini + P3_Filter) × alle 3 Inputs × 3 Reps, einmal
mit Standard-DB (Vorher) und einmal mit verbesserten custom-Einträgen (Nachher).

**Skript**: `benchmark/custom_entries_experiment.py`

Aufruf:
```
python benchmark/custom_entries_experiment.py \
    --config benchmark/custom_entries_config.json \
    --baseline-runs benchmark_output/ablation_<ts>/benchmark_runs.json
```

**Config-Format** (`custom_entries_config.json`, basierend auf Template):
- `action: "update"` — überschreibt Felder eines bestehenden Eintrags in DB-Kopie
- `action: "insert"` — fügt neuen custom-Eintrag ein (source='custom')
- Felder: `id`, `name`, `klassifizierung`, `technischeBeschreibung`, `anmerkungen` u.a.
- Die originale DB wird nicht verändert — Experiment läuft gegen isolierte Kopie

**Isolierung**: Das Skript kopiert `data/oekobaudat.db` → `custom_entries_<ts>/oekobaudat_modified.db`
und setzt `LOCAL_DB_PATH` per ENV nur für die Nachher-Subprocess-Läufe.

**Output**: `benchmark_output/custom_entries_<ts>/custom_entries_report.html` mit
Vorher-Nachher-Accuracy pro Schicht und Input, Änderungs-Tabelle, Paper-Summary-Entwurf.

**Paper-Positionierung**: Abschnitt nach Hauptablation, „Sensitivity to Database Coverage"
oder Diskussion/Future Work. Kernaussage: Die Methode skaliert mit der Datenbankqualität —
bessere EPD-Beschreibungen verbessern Accuracy direkt.

**Adressierte Reviewer-Kritik**: Reviewer 1, Punkt 1: „Sparse EPD data not addressed."

**Vorbedingung**: Vor Ausführung müssen Ground-Truth-UUIDs für alle 3 Inputs bestimmt sein.
Ohne `ground_truth.json` läuft das Skript durch, gibt aber keine Accuracy aus.

---

## 6. Offene Punkte (TODO)

- [x] Material-Werte für Input A, B, C festgelegt (`TestInput/ablation_a/b/c/input/input.json`)
- [ ] Ground-Truth-UUIDs manuell bestimmen (nach Benchmark-Lauf + Template-Review)
- [ ] `custom_entries_config.json` erstellen (aus Template, UUIDs nach ÖKOBAUDAT-Lookup)
- [ ] Prompt-Beispiel dokumentieren (Abschnitt 4.2)
- [ ] Snapshot-Datum der lokalen ÖKOBAUDAT-DB dokumentieren
- [ ] Preisdatum der 4 Azure-Modelle für v2 dokumentieren (neue Benchmark-Läufe)
- [ ] Referenzen Hofmeyer et al. 2023 und Chen et al. 2024 sichten (Reviewer 2)
- [ ] Limitation Open-Source-LLMs ausformulieren

---

## 7. Reviewer-Kritik — Adressierungsstatus

| Reviewer | Kritikpunkt | Adressierung | Status |
|----------|------------|--------------|--------|
| R1+R2 | Einzelner Testfall | 3 diverse Inputs (A/B/C) | ✅ Design beschlossen |
| R2 | Cost-Efficiency-Score fragwürdig | Cost-at-Threshold ersetzt ihn | ✅ Design beschlossen |
| R2 | Prompt-Design nicht erklärt | Prompt-Beispiel ins Paper | ⏳ TODO |
| R2 | Kombinationsauswahl unbegründet | Vollständige Faktorielle begründen | ✅ Antwort formuliert |
| R2 | Fehlende Refs (Hofmeyer, Chen) | Literatur sichten | ⏳ TODO |
| R1 | Sparse EPD data | Custom-Entries-Experiment | ✅ Design beschlossen |
| R2 | Token-Kosten nur kommerziell | Als Limitation im Paper nennen | ✅ Formulierung bereit |
| R1 | Neuheitsabgrenzung fehlt | Im Related-Work-Abschnitt schärfen | ⏳ TODO |
| R1 | Architektur des Tools | Bessere Beschreibung + Diagramm | ⏳ TODO |
| R1 | IFC-Datenqualität Straßen | Im Background-Abschnitt ergänzen | ⏳ TODO |
