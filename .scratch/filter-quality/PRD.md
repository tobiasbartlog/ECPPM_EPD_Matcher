# PRD: Filter-Qualität – Präzision & Recall für Tiefbau-EPDs

Status: ready-for-agent

---

## Problem Statement

Der EPD-Vorfilter (Stage 3) produziert zwei Klassen von Fehlern, die die Qualität
des LLM-Matchings und damit die Validität der Ablationsstudie untergraben:

**Zu viele falsche EPDs (Precision-Problem):**
Für Asphalt-Materialien (SMA, AC) landen Hochbau-EPDs wie Teppichfliesen,
Brausesets und Lüftungsgeräte im Prompt neben den echten Asphalt-EPDs. Ursache:
`_ist_generisch_asphalt` trifft auf "bitumen" im EPD-Text – auch Teppichfliesen
haben eine Bitumen-Trägerplatte und enthalten deshalb den Begriff. Die aktuelle
AUSSCHLUSS-Liste kennt nur 8 produktspezifische Begriffe (Mörtel, Ziegel usw.)
und ist kein skalierbares Muster.

**Falsche EPDs für ungebundene Tiefbau-Schichten (Recall-Problem):**
Für STSuB (Schotter-Tragschicht ungebunden) gibt der Filter 4 Stahlblech-EPDs
zurück. Ursache ist ein zweistufiger Bug: (1) "STSuB" wird nicht als
Schotter-Material erkannt, sodass der Fallback-Pfad (Fall 3) greift; (2) Fall 3
sucht nach Wörtern mit len > 2 aus dem kombinierten Material+Schicht-Text –
"nicht" (5 Zeichen, kein Stoppwort) trifft auf "nicht-schlussgeglüht" in
Stahlblech-EPD-Namen. Das Ergebnis: das LLM sieht keine relevanten EPDs und
gibt 0 Matches zurück, obwohl passende Schotter-EPDs in der DB vorhanden sind.

Beide Fehler wurden durch systematische Analyse von 94 Benchmark-Runs (8 Configs
× 4 Modelle × 3 Inputs) empirisch bestätigt.

---

## Solution

### Ansatz A – Klassifikations-Whitelist (generische Lösung für Precision)

Statt einzelne Produkt-Begriffe auf eine Blacklist zu setzen (Whack-a-Mole),
wird für Asphalt-Materialien eine **positive Klassifikations-Prüfung** eingeführt:
Eine EPD darf nur dann als Asphalt-Kandidat gelten, wenn ihr `klassifizierung`-Feld
zu einem erlaubten Tiefbau-Pfad gehört.

Erlaubte Klassifikations-Präfixe (Ökobaudat-Hierarchie):
- `Mineralische Baustoffe / Asphalt`
- `Mineralische Baustoffe / Zuschläge`
- `Mineralische Baustoffe / Beton` *(optional, für Betonfahrbahn)*
- `Mineralische Baustoffe / Pflastersteine` *(optional)*

EPDs aus `Kunststoffe`, `Gebäudetechnik`, `Dämmstoffe`, `Metalle` usw. werden
damit strukturell ausgeschlossen, ohne dass produktspezifische Begriffe gepflegt
werden müssen. Der Ansatz ist stabil gegenüber neuen EPD-Einträgen, weil die
Ökobaudat-Klassifikationshierarchie sich selten ändert.

### Ansatz B – STSuB + FSS Kategorie-Erkennung (Recall-Fix)

Das MATERIAL_KATEGORIEN-Dict in `asphalt_glossar.py` wird um
Tiefbau-spezifische Keywords erweitert, sodass STSuB und ähnliche Codes direkt
in die Kategorie "schotter" / "frostschutz" fallen, anstatt den Fallback-Pfad
zu betreten.

Zu ergänzen:
- `schotter`: `"stsub"`, `"ungebunden"`, `"schottertrag"`, `"stuetzschicht"`, `"gnb"`, `"rcb"`
- `frostschutz`: `"fss"`, `"fsk"`, `"fsks"`

### Ansatz C – stop_words-Fix (Fall-3-Bug)

In der Fall-3-Keyword-Suche wird `"nicht"` zu den Stoppwörtern hinzugefügt
(und weitere grammatikalische Negationen/Artikel: `"kein"`, `"ohne"`, `"auch"`).
Alternativ: Mindestlänge von 2 auf 4 erhöhen, um kurze, mehrdeutige Fragmente
generell auszuschließen.

---

## User Stories

1. Als Forscher möchte ich, dass der Filter für `AC 16 B S` ausschließlich EPDs aus
   der Asphalt/Zuschläge-Klassifikation zurückgibt, damit das LLM keine Teppichfliesen-
   oder Sanitär-EPDs als Kandidaten bewertet.

2. Als Forscher möchte ich, dass der Filter für `STSuB 0/45` Schotter-EPDs
   zurückgibt (nicht Stahlblech-EPDs), damit das LLM für ungebundene Tragschichten
   valide Matches finden kann.

3. Als Forscher möchte ich, dass der Filter für `FSS 0/32` und `Gesteinskörnungsgemisch 0/32`
   relevante Frost­schutz-/Zuschlag-EPDs zurückgibt.

4. Als Forscher möchte ich, dass die Precision-/Recall-Qualität des Filters
   automatisiert messbar ist (Testfälle mit bekannten Erwartungswerten), damit
   Regressions nach Code-Änderungen sofort sichtbar werden.

5. Als Forscher möchte ich, dass die Whitelist der erlaubten Klassifikations-Pfade
   in einer zentralen, gut sichtbaren Konstante steht (nicht verstreut im Code),
   damit ich sie bei Bedarf erweitern kann (z.B. für Betonfahrbahn-EPDs).

6. Als Forscher möchte ich, dass nach den Filter-Fixes ein vollständiger
   Benchmark-Neurun für die Filter-relevanten Configs (P3, P6, P7, P8) durchgeführt
   wird, damit die Studienergebnisse auf sauberen Daten basieren.

7. Als Forscher möchte ich, dass die 2 fehlgeschlagenen Runs (ablation_a | P1_Baseline |
   gpt-5-nano und ablation_b | P3_Filter | gpt-5.2-chat) erneut ausgeführt und in den
   bestehenden `benchmark_runs.json` gemergt werden.

8. Als Forscher möchte ich, dass der Filter im Debug-Modus pro Material ausgibt,
   welche Klassifikations-Pfade akzeptiert/abgelehnt wurden, damit ich die
   Whitelist empirisch validieren kann.

---

## Implementation Decisions

### Modul 1 – Klassifikations-Whitelist in `matching_rules.py`

Eine neue Konstante `TIEFBAU_KLASSIFIKATION_PREFIXES: List[str]` definiert die
erlaubten Ökobaudat-Klassifikationspfade. Eine neue Funktion
`ist_tiefbau_relevant(epd: Dict) -> bool` prüft, ob `epd["klassifizierung"]`
mit einem dieser Prefixe beginnt (case-insensitive).

Diese Funktion wird in `bewerte_kandidat` als zusätzliches Fakt in `Bewertung`
integriert (`ist_tiefbau: bool`). `EPDFilter` Fall 1 nutzt dieses Fakt, um
Nicht-Tiefbau-EPDs auszuschließen, bevor `ist_asphalt` geprüft wird.

Vorteil: Die Whitelist ist die einzige Pflegestelle für Tiefbau-Scope-Entscheidungen.
Sie ist domänenfachlich motiviert (Ökobaudat-Hierarchie), nicht
produktspezifisch (Teppich, Sanitär).

### Modul 2 – STSuB/FSS-Keywords in `asphalt_glossar.py`

`MATERIAL_KATEGORIEN` wird um die genannten Keywords erweitert. Keine
Änderung an der Logik – nur Daten.

### Modul 3 – stop_words-Fix in `epd_filter.py`

Fall 3: `stop_words`-Set erweitern um `"nicht"`, `"kein"`, `"ohne"`, `"auch"`,
`"sein"`, `"wird"`, `"beim"`. Alternativ: `len(w) > 3` statt `> 2` als einfachere
und robustere Schwelle.

### Merge-Strategie für Neurun

Der Ablations-Benchmark soll nach den Fixes für P3/P6/P7/P8 (alle Modelle,
alle Inputs, 1 Rep) neu ausgeführt werden. Ergebnisse werden in einen neuen
`benchmark_runs_v2.json` geschrieben. P1/P2/P4/P5 (kein Filter) bleiben aus
dem alten Run – sie sind nicht von Filter-Fixes betroffen und so teuer, dass
ein Neurun vermieden werden soll.

### Keine Änderung an Stage 5

Die Confidence-Validation (ConfidenceValidator) bleibt unverändert. Sie arbeitet
korrekt – das Problem liegt ausschließlich in Stage 3.

---

## Testing Decisions

**Was einen guten Test ausmacht:**
Tests prüfen das beobachtbare Verhalten der Filterung (welche EPDs kommen rein,
welche nicht), nicht die interne Implementierung (welcher Code-Pfad genommen wird).
Ein Test gibt eine Liste von Mock-EPDs vor und prüft, ob der Filter
die erwartete Teilmenge zurückgibt.

**Zu testende Module:**

1. `ist_tiefbau_relevant(epd)` – Unit-Tests:
   - Asphalt-EPD mit Klassifizierung `"Mineralische Baustoffe / Asphalt / Tragschichten"` → True
   - Teppich-EPD mit `"Kunststoffe / Bodenbeläge / Textile Bodenbeläge"` → False
   - Sanitär-EPD mit `"Gebäudetechnik / Sanitär / Armaturen"` → False
   - Zuschlag-EPD mit `"Mineralische Baustoffe / Zuschläge / Natürliche Gesteinskörnungen"` → True

2. `EPDFilter.filter_for_single_material` – Integrations-Tests mit den
   Problemmaterialien aus dem Benchmark:
   - `("STSuB 0/45", "Nicht bituminöse Tragschicht")` → alle zurückgegebenen EPDs
     sind aus `Mineralische Baustoffe / Zuschläge`, keine Stahlblech-EPDs
   - `("SMA 11 S", "Deckschicht")` → keine EPD aus `Kunststoffe` oder `Gebäudetechnik`
   - `("AC 16 B S", "Binderschicht")` → `Asphaltbinder`-EPD ist im Ergebnis

3. `_detect_material_category` – Unit-Tests:
   - `("STSuB 0/45", "Nicht bituminöse Tragschicht")` → `"schotter"`
   - `("FSS 0/32", "Frostschutzschicht")` → `"frostschutz"`

Prior art: `matching/epd_filter.py` und `matching/matching_rules.py` haben
bereits `if __name__ == "__main__":`-Testblöcke als Muster. Tests sollten
als eigenständige `pytest`-Datei unter `tests/` geschrieben werden (noch kein
`tests/`-Verzeichnis vorhanden – anlegen).

---

## Out of Scope

- Neurun von P1/P2/P4/P5 (kein Filter): diese Configs sind von den Filter-Fixes
  nicht betroffen; die hohen Token-Kosten (~$3–4) sind nicht gerechtfertigt.
- Ground-Truth-Erstellung: die Ablations-Analyse benötigt Ground-Truth-JSONs pro
  Input-Ordner – dies ist eine fachliche Entscheidung (welche EPD ist der
  "richtige" Match), kein Code-Problem. Liegt außerhalb dieser PRD.
- Änderungen an Stage 4 (LLM-Prompt) oder Stage 5 (ConfidenceValidator).
- Erweiterung des Glossars auf andere Tiefbau-Materialien (z.B. Betonfahrbahn,
  Pflaster): das ist ein separates Feature.
- Fehler-Analyse für gpt-5-nano Batch-Failures in ablation_a/b: valide
  Studiendaten, kein Bug.

---

## Further Notes

**Warum keine Blacklist:**
Eine wortbasierte Blacklist (z.B. `"teppich"`, `"sanitär"`) ist fragil – sie
wächst mit jeder neuen EPD-Art, die durch das Netz fällt. Die
Ökobaudat-Klassifikationshierarchie ist stabiler und domänenfachlich motiviert:
Tiefbau-relevante EPDs liegen immer unter `Mineralische Baustoffe`.

**Risiko der Whitelist:**
Falls die Ökobaudat zukünftig Tiefbau-EPDs unter einer neuen
Klassifikationskategorie führt (unwahrscheinlich, aber möglich), wären diese
zunächst gefiltert. Deshalb sollte die Whitelist gut dokumentiert und der
Debug-Modus zugänglich sein.

**Benchmarkkontext:**
Der Befund aus 94 Runs: P7_BatchFilter ist die beste Config (5/5 Layers
gematcht, avg confidence 67.9%, 36% high-confidence Matches, 270× Token-Reduktion
vs. P1_Baseline). Filter-Fixes verbessern P3/P6/P7/P8 weiter. P1/P4 bleiben
bewusst unkorrekt als Baseline für die Ablationsstudie.

**Prioritätsreihenfolge für die Implementierung:**
1. Klassifikations-Whitelist (größte Wirkung, sauberer Ansatz)
2. STSuB/FSS-Keywords (zweithöchster Recall-Impact)
3. stop_words-Fix (kleinster, aber schnellster Fix)
4. Tests
5. Benchmark-Neurun P3/P6/P7/P8
6. Fehler-Runs mergen
