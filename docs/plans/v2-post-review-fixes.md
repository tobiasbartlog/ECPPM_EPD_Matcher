# Plan — v2 Post-Review-Fixes (Code-Review-Befunde nach Filter-Quality-Implementierung)

> **Zweck:** Umsetzungsplan für die acht Defekte aus dem systematischen Code-Review nach
> der Filter-Quality-Implementierung. Vollständige Problemdefinition und User Stories:
> `.scratch/v2-post-review-fixes/PRD.md`.

---

## Prioritätsreihenfolge

### P0 — Studien-kritisch (vor dem 5-Rep-Lauf)

**Befund 1 — ablation_b Ground-Truth-Template korrigieren**
- Datei: `TestInput/ablation_b/ground_truth_template.json`
- Aktion: `suggested_uuid` für „Nicht bituminöse Tragschicht" von `9795c91c`
  (Asphalttragschicht) auf `f4461491` (Schotter 16/32) setzen. Phase-A-Tabelle
  (paper_design.md §1.2.4) belegt 20/24 Modell-Config-Kombinationen für diese UUID.
  `epd_name` entsprechend auf `"Schotter 16/32"` setzen.

**Befund 2 — filter_trace.py Fixtures kanonisieren**
- Datei: `tools/filter_trace.py`
- Aktion: `FIXTURE_EPDS` fix-02 bis fix-05 von `"Asphalt / Deckschichten"` etc.
  auf `"Mineralische Baustoffe / Asphalt / Deckschichten"` usw. umstellen.
  Mindestens eine Nicht-Tiefbau-Fixture (z.B. Teppichfliese) als expliziten
  Whitelist-Kontrollfall behalten und kommentieren.

---

### P1 — Korrektheitsfixes (parallelisierbar)

**Befund 3 — Fall-3-Cap wiederherstellen**
- Datei: `matching/epd_filter.py`
- Aktion: `return all_epds[:50], []` statt `return all_epds, []` wenn
  `material_words` leer ist (Zeile ~196). Optional konfigurierbarer Parameter.

**Befund 5 — Fall-2-sekundär len-Schwelle angleichen**
- Datei: `matching/epd_filter.py`
- Aktion: `len(w) > 3` → `len(w) > 2` in Zeile ~171 (Fall 2 sekundärer Fallback).

**Befund 6 — Stage-5-Annotation Einzelmodus fixen**
- Datei: `matching/azure_matcher.py`
- Aktion: `original_conf = match.get("confidence", 50)` vor `match["confidence"] = new_conf`
  sichern; `if new_conf != original_conf` statt `if new_conf != match.get("confidence")`.

---

### P2 — Prophylaktisch / Wartung (nach dem Paper-Lauf)

**Befund 4 — Fuzzy-Match Negativ-Kontext**
- Datei: `utils/asphalt_glossar.py`
- Aktion: `_fuzzy_match_asphalt_type` soll für AC-Typ-`fuzzy_matches` `"bitumen"` nicht
  matchen, wenn ein Negativ-Kontext-Begriff im Text vorkommt. Option A: Negativ-Kontext-
  Check in `_fuzzy_match_asphalt_type` vor dem Match einbauen.
- Hinweis: Trifft das v2-Testset nicht; prophylaktisch für künftige Inputs.

**Befund 7 — Toter Import entfernen**
- Datei: `matching/prompt_builder.py`
- Aktion: `filter_epds_for_material` aus dem Import-Block entfernen.
  Deprecation-Kommentar in `asphalt_glossar.py` ergänzen.

**Befund 8 — Betonpflaster-Testfall aktualisieren**
- Datei: `matching/matching_rules.py`
- Aktion: Entweder `klassifizierung` auf einen Whitelist-konformen Pfad umstellen
  (z.B. `"Mineralische Baustoffe / Mörtel und Beton / Beton"`) oder Kommentar
  ergänzen, dass der Test `bewerte_kandidat` in Isolation prüft (nicht den Produktions-
  Pfad, der die EPD durch die Whitelist filtert).

---

## Abhängigkeiten

```
Befund 1 (Ground Truth) ──→ manueller Review ──→ 5-Rep-Lauf
Befund 2 (filter_trace) ──→ sofort umsetzbar
Befunde 3, 5, 6 ──→ unabhängig voneinander, kein Benchmark-Neurun nötig
Befunde 4, 7, 8 ──→ nach Paper-Einreichung oder parallel
```

## Referenzen

- PRD: `.scratch/v2-post-review-fixes/PRD.md`
- Phase-A-Ergebnisse: `docs/studie/paper_design.md` §1.2.4
- Filter-Quality-PRD (abgeschlossen): `.scratch/filter-quality/PRD.md`
