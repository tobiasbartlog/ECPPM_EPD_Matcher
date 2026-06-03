Status: needs-triage

# PRD: v2 Post-Review Fixes — Code-Review-Befunde nach Filter-Quality-Implementierung

---

## Problem Statement

Nach der Implementierung der Filter-Quality-Fixes (Tiefbau-Scope-Whitelist, STSuB-Keywords,
Negativ-Kontext-Logik in `_ist_generisch_asphalt`) hat ein systematisches Code-Review acht
Defekte aufgedeckt, die die Korrektheit der Ablationsstudie und die Zuverlässigkeit des
Entwicklungs-Toolings beeinträchtigen:

**Studienrelevante Befunde:**
1. Das Ground-Truth-Template für ablation_b „Nicht bituminöse Tragschicht" empfiehlt
   `9795c91c` (Asphalttragschicht). **Nuancierung nach Validierung**: Das ist *kein*
   Pipeline-Bug, sondern eine bewusste Forscher-Entscheidung. Der Input ist konzeptionell
   inkonsistent (NAME=„Nicht bituminöse Tragschicht", MATERIAL=„AC 32 T S mit Straßenbau-
   bitumen 30/45"=Asphalt) — das ist beabsichtigte Eigenschaft des „B_Praxis"-Szenarios.
   Im 5-Rep-Lauf wählt das LLM über alle 8 Configs überwiegend `9795c91c` (Pre-Fix:
   24/28). Die Vorlage spiegelt den Modell-Konsens korrekt wider; offen ist nur die
   methodische Entscheidung, ob die Schicht aus der Accuracy ausgeschlossen wird
   (`null`) oder der Konsens akzeptiert wird. Siehe `paper_design.md` §1.2.5.
2. `_fuzzy_match_asphalt_type` matcht „bitumen" als AC-Typ bevor `_ist_generisch_asphalt`
   aufgerufen wird. Der Negativ-Kontext-Fix greift damit für Eingabematerialien wie
   „Bitumenbahn G200" nicht (sie werden weiterhin als Asphalt klassifiziert).
   **v2-Effekt: keiner** (kein v2-MATERIAL trifft diese Bedingung — „Straßenbaubitumen"
   wird zuvor von `_parse_normierte_bezeichnung("AC 32 T S …")` abgefangen).

**Tool-relevante Befunde:**
3. Die Fixture-EPDs in `filter_trace.py` verwenden kurze, nicht-kanonische
   Klassifizierungspfade (z.B. `"Asphalt / Deckschichten"` statt
   `"Mineralische Baustoffe / Asphalt / Deckschichten"`). Die neue Whitelist
   filtert sie still heraus; das Trace-Tool liefert für alle betroffenen Fixtures
   leere Ergebnisse, was Paper-Analysen korrumpiert.
4. Fall 3 in `EPDFilter._filter_epds` gibt bei leerem `material_words` die gesamte
   Whitelist-gefilterte Liste (~319 EPDs) ohne Obergrenze zurück. Die alte
   `filter_epds_for_material`-Funktion hatte einen `min(50, max_epds)`-Cap als
   Sicherheitsnetz.

**Code-Qualitäts-Befunde:**
5. Fall-2-sekundärer Fallback und Fall 3 verwenden unterschiedliche Token-Längen­schwellen
   (`len > 3` vs. `len > 2`). Paper-Design §1.2.2 begründet `len > 2` explizit für
   3-Buchstaben-Codes wie OPA; Fall 2 sekundär wendet das nicht an.
6. `azure_matcher.py` mutiert `match["confidence"]` bevor verglichen wird, ob sich der
   Wert geändert hat. Die „[Korrigiert: ...]"-Annotation wird im Einzelmodus nie geschrieben.
7. `prompt_builder.py` importiert `filter_epds_for_material`, obwohl die Funktion nirgendwo
   aufgerufen wird. Sie divergiert in vier Punkten von der aktiven `EPDFilter._filter_epds`
   und ist ein Wartungs-Fallstrick.
8. Der Betonpflaster-Testfall in `matching_rules.py __main__` testet eine EPD mit
   `klassifizierung = "Mineralische Baustoffe / Pflastersteine"`, die in der Produktions-
   Pipeline bereits durch die Whitelist gefiltert wird, bevor `bewerte_kandidat` aufgerufen
   wird. Der Test deckt einen toten Code-Pfad ab.

---

## Solution

Sieben kleine Code-Fixes plus eine Forscher-/Experten-Entscheidung:

1. **ablation_b Ground-Truth-Entscheidung** (kein Code-Fix, methodische Wahl): Vorläufig
   `suggested_uuid = null` im Template gesetzt. Experten-Review entscheidet final, ob die
   Schicht aus der Accuracy ausgeschlossen wird (`null` → 4-von-5-Auswertung) oder der
   Modell-Konsens `9795c91c` akzeptiert wird (NamePref-Kontroll-Schicht). Begründung im
   Paper-Methodikteil dokumentieren (Vorlage: `paper_design.md` §1.2.5).
2. **filter_trace.py Fixtures** auf kanonische Klassifizierungspfade umstellen.
3. **Fall 3 Cap** wiederherstellen: `return all_epds[:50], []` (oder konfigurierbarer Wert).
4. **Fuzzy-Match Negativ-Kontext**: `_fuzzy_match_asphalt_type` oder den Step-2-Aufruf in
   `parse_material_input` so anpassen, dass Eingabetexte mit Negativ-Kontext nicht als
   Asphalt-Typ klassifiziert werden.
5. **Fall-2-sekundär len-Schwelle** von `> 3` auf `> 2` angleichen.
6. **Stage-5-Annotation im Einzelmodus** fixen: Wert vor der Mutation sichern, dann vergleichen.
7. **Toten Import** in `prompt_builder.py` entfernen.
8. **Betonpflaster-Testfall** in `matching_rules.py` aktualisieren: entweder auf eine
   Whitelist-konforme Klassifizierung umstellen oder kommentieren, dass die EPD in der
   Live-Pipeline die Whitelist nie übersteht.

---

## User Stories

1. Als Forscher möchte ich, dass das Ground-Truth-Template für ablation_b/
   „Nicht bituminöse Tragschicht" eine Schotter-EPD (oder `null`) vorschlägt,
   damit ich beim manuellen Review nicht die falsche UUID als Ground Truth setze
   und die Accuracy-Berechnung korrumpiere.

2. Als Forscher möchte ich, dass `filter_trace.py` für alle Asphalt-Fixtures
   nicht-leere Trace-Ausgaben liefert, damit das Tool als Erklärungs- und
   Validierungsartefakt für den Paper-Anhang nutzbar bleibt.

3. Als Forscher möchte ich, dass ein Eingabematerial mit „Bitumenbahn" im Namen
   nicht als Asphalt-Material klassifiziert wird, damit Stage 3 für solche Inputs
   den richtigen Filterpfad (Abdichtung/Fall 2 oder Fall 3) nimmt.

4. Als Entwickler möchte ich, dass ein Eingabematerial mit ausschließlich
   Stoppwörtern oder sehr kurzen Tokens nicht die gesamte Whitelist an Stage 4
   übergibt, damit Token-Kosten und Modell-Kontext nicht unkontrolliert wachsen.

5. Als Entwickler möchte ich, dass 3-Buchstaben-Codes (OPA, fss) sowohl in
   Fall 3 als auch im sekundären Fallback von Fall 2 berücksichtigt werden,
   damit die Keyword-Suche konsistent ist.

6. Als Entwickler möchte ich, dass Stage-5-Korrekturen im Einzelmodus in der
   „begruendung"-Spalte des Outputs sichtbar sind, damit ich Confidence-Kappungen
   debuggen kann ohne den Code zu ändern.

7. Als Entwickler möchte ich, dass `prompt_builder.py` keine toten Imports hat,
   damit neue Mitarbeiter nicht versehentlich die veraltete `filter_epds_for_material`
   nutzen und stille Fehler einführen.

8. Als Entwickler möchte ich, dass alle Testfälle in `matching_rules.py` EPDs
   beschreiben, die in der Live-Pipeline tatsächlich `bewerte_kandidat` erreichen,
   damit die Tests die Produktionsbedingungen korrekt widerspiegeln.

9. Als Forscher möchte ich, dass nach der ablation_b Ground-Truth-Korrektur ein
   Testlauf für ablation_b bestätigt, dass der Benchmark die richtigen UUIDs
   evaluiert.

---

## Implementation Decisions

### Befund 1 — ablation_b „Nicht bituminöse Tragschicht" Ground-Truth

**Korrektur der ursprünglichen Annahme**: Die §1.2.4-Phase-A-Tabelle mit „20/24 Schotter
16/32" bezog sich auf die STSuB-Schicht in **ablation_a**, nicht auf ablation_b. Für
ablation_b ist `9795c91c` (Asphalttragschicht) im Pre-Fix-Lauf mit 24/28 dominant und
auch im Post-Fix-5-Rep-Lauf der LLM-Konsens über alle 8 Configs — weil das MATERIAL-Feld
„AC 32 T S mit Straßenbaubitumen 30/45" die Asphalt-Klassifizierung signalisiert.

**Vorläufige Aktion (umgesetzt)**: `suggested_uuid = null` im Template gesetzt, mit
ausführlicher Note. Wartet auf Experten-Validierung.

**Optionen für die finale Entscheidung** (Expert + Forscher):
- **(a) `null`** → Schicht aus Accuracy ausschließen (per §2.2). Konservativ, vermeidet
  semantische Streitfälle, kostet eine Schicht von ablation_b.
- **(b) `9795c91c`** → Konsens akzeptieren. ablation_b wird zur Kontroll-Schicht für
  NamePref-Verhalten bei Input-Konflikten; NamePref=true (P4/P5/P6/P8) und NamePref=false
  (P1/P2/P3/P7) sollten systematisch unterschiedlich abschneiden.

Begründung der gewählten Option im Paper unter „Methodische Annahmen" dokumentieren.

### Befund 2 — filter_trace.py Fixtures

Alle Fixture-EPDs, deren `klassifizierung` nicht mit einem der drei
`TIEFBAU_KLASSIFIKATION_PREFIXES` beginnt, müssen auf kanonische Pfade umgestellt
werden (z.B. `"Asphalt / Deckschichten"` → `"Mineralische Baustoffe / Asphalt / Deckschichten"`).
Eine Ablation-relevante Nicht-Tiefbau-Fixture (z.B. Teppichfliese) sollte explizit als
„Whitelist-ausgeschlossen"-Kontrollfall behalten und kommentiert werden.

### Befund 3 — Fall-3-Cap

`EPDFilter._filter_epds` erhält einen optionalen `max_fallback`-Parameter (Default: 50).
Der `return all_epds, []`-Zweig in Fall 3 verwendet `all_epds[:max_fallback]`.
Kein `max_epds`-Parameter nötig – der einzige Unbegrenzt-Rückgabepfad ist dieser Zweig.

### Befund 4 — Fuzzy-Match Negativ-Kontext

Option A (minimal): `_fuzzy_match_asphalt_type` überspringt die AC-`fuzzy_matches`-Prüfung
auf `"bitumen"` und `"bituminös"`, wenn der Text einen Negativ-Kontext-Begriff enthält.
Option B (sauber): `parse_material_input` prüft nach Step 2, ob `_ist_generisch_asphalt`
für denselben Text `False` zurückgeben würde, und setzt `ist_asphalt=False` wenn nötig.
Empfehlung: Option A, da der Fix minimal ist und keine neue Abstraktion einführt.

### Befund 5 — Fall-2-sekundär len-Schwelle

Einzeilige Änderung: `len(w) > 3` → `len(w) > 2` in `_filter_epds` Fall 2 Sekundär-Fallback
(Zeile 171). Gleiche Logik wie Fall 3 (Zeile 193).

### Befund 6 — Stage-5-Annotation Einzelmodus

In `azure_matcher.py`: `original_conf = match.get("confidence", 50)` vor der Zuweisung,
dann `if new_conf != original_conf` prüfen. Entspricht dem Muster in `validate_batch_results`.

### Befund 7 — Toter Import

`filter_epds_for_material` aus dem Import-Block in `prompt_builder.py` entfernen.
Die Legacy-Funktion selbst in `asphalt_glossar.py` bleibt vorerst bestehen (kein Scope-Creep),
aber erhält einen Deprecation-Kommentar mit Verweis auf `EPDFilter`.

### Befund 8 — Betonpflaster-Testfall

Entweder: EPD-`klassifizierung` auf `"Mineralische Baustoffe / Mörtel und Beton / Beton"`
setzen (Whitelist-konform) und erwartetes Verhalten anpassen. Oder: Test mit Kommentar
versehen, der erklärt, dass diese EPD in der Pipeline durch die Whitelist gefiltert wird,
und der Test das Verhalten von `bewerte_kandidat` in Isolation prüft.

---

## Testing Decisions

**Was einen guten Test ausmacht:**
Tests prüfen das beobachtbare Ausgabeverhalten (welche EPD-IDs kommen raus, welche
Confidence-Werte werden zurückgegeben), nicht interne Implementierungsdetails.
Mock-EPDs sollen alle relevanten Klassifizierungspfade abdecken, inklusive
Whitelist-Grenzfälle.

**Zu testende Module:**

- `filter_trace.py`: Nach Fixture-Update Smoke-Test, der für jeden Fixture-Fall
  eine nicht-leere Ausgabe liefert.
- `EPDFilter._filter_epds` Fall-3-Cap: Testfall mit Material = Stoppwort-only,
  prüft `len(result) <= 50`.
- `parse_material_input` + Negativ-Kontext: Testfall `"Bitumenbahn G200"` →
  `ist_asphalt=False`.
- Stage-5-Annotation: Testfall in Einzelmodus, prüft dass `begruendung` den
  `[Korrigiert: ...]`-String enthält, wenn Confidence gekappt wurde.

**Prior Art:**
Die bestehenden `if __name__ == "__main__":`-Blöcke in `matching_rules.py` und
`epd_filter.py` dienen als Muster für zusätzliche Testfälle.

---

## Out of Scope

- Vollständiger Neurun des 5-Rep-Benchmarks (480 Runs): erst nach Ground-Truth-Finalisierung.
- Löschen von `filter_epds_for_material` aus `asphalt_glossar.py`: separates
  Cleanup-Ticket, da CLAUDE.md auf die Funktion verweist.
- Erweiterung der `negativ_kontext`-Liste für neue DB-Einträge: das ist ein laufendes
  Wartungs-Thema, kein Post-Review-Fix.
- Ablation-Schalter für die Whitelist (bereits in paper_design.md §1.2.2 begründet
  abgelehnt): kein neuer Schalter.

---

## Further Notes

**Priorisierung für den Paper-Deadline-Pfad:**
Der vollständige 5-Rep-Benchmark-Lauf (480 Runs) ist bereits am 2026-06-02 abgeschlossen
(Commit `a159897`). Befund 1 ist eine methodische Entscheidung beim Ground-Truth-Review
und blockiert nur die Auswertung (`ablation_analysis.py`), nicht den Pipeline-Code.
Befunde 2–8 sind technische Schulden ohne Einfluss auf die v2-Studiendaten und können
nach Paper-Einreichung bereinigt werden.

**Studienvalidität bestätigt:**
Eine systematische Analyse aller acht Befunde gegen die v2-Eingabematerialien hat ergeben,
dass keiner einen Effekt auf die 480 Runs hat. Details in `paper_design.md` §1.2.5
(Tabelle „Effekt auf v2-Daten").

**Befund 4 trifft das v2-Testset nicht:**
Kein v2-MATERIAL enthält „bitumenbahn" oder ähnliche Negativ-Kontext-Terme.
„Straßenbaubitumen 30/45" im ablation_b-Input wird zuerst von `_parse_normierte_bezeichnung`
abgefangen (AC-Code an Stelle 0), bevor `_fuzzy_match_asphalt_type` aufgerufen wird —
der Fuzzy-Pfad ist für v2 nicht erreichbar.

**Befund 6 ist pre-existing:**
Der Stage-5-Annotationsbug in `azure_matcher.py` wurde nicht durch die v2-Änderungen
eingeführt. Er betrifft ausschließlich Debug-Ausgaben (begruendung-Feld), nicht die
Confidence-Werte selbst. Alle Accuracy-Metriken sind korrekt.
