# Implementierungsplan — Matching-Wissen in `matching_rules` konsolidieren

> **Für den umsetzenden Agenten (Sonnet):** Dies ist eine *reine Extraktion/Konsolidierung*,
> kein Funktions-Neubau. Verhalten muss vor/nach dem Refactor identisch sein (siehe
> Regressionsschutz). Vokabular: siehe `CONTEXT.md` (`matching_rules`, `Bewertung`,
> `5-Stage-Pipeline`, `Ablations-Schalter`).

## Ziel

Das Wissen darüber, *ob ein EPD-Kandidat zu einem Material passt*, liegt heute dreifach:

| Wissen | Heute in | Genutzt von |
|---|---|---|
| Ausschluss-Begriffe | `utils/asphalt_glossar.py` → `AUSSCHLUSS_BEGRIFFE` | Stage 3 **und** Stage 5 |
| „ist Asphalt?“ | `asphalt_glossar.py` → `_ist_generisch_asphalt` + Typ-Suchbegriffe | Stage 3 **und** Stage 5 |
| Kategorie-/Typ-Mismatch | `MATERIAL_KATEGORIEN[...]["ausschluss"]` (glossar) **vs.** `MATERIAL_MISMATCHES` (epd_filter) | getrennt dupliziert |
| Schicht-Treffer | `schicht_muss in combined` | Stage 3 **und** Stage 5 |

Diese Prädikate werden in **Stage 3** (`filter_epds_for_material`) und **Stage 5**
(`ConfidenceValidator.validate_match`) jeweils eigenständig neu berechnet. Ziel: ein tiefes Modul
`matching/matching_rules.py`, das die Prädikate **einmal** als `Bewertung` liefert; Stage 3 und
Stage 5 werden dünne Aufrufer.

## Invarianten — NICHT brechen

1. **5 Stage-Grenzen bleiben.** Eine Config-Klasse pro Stage in `settings.py`. Stage 2 (Parsing)
   bleibt in `asphalt_glossar.py`.
2. **Die 3 Ablations-Schalter** (`EPD_USE_BATCH_MODE`, `EPD_USE_GLOSSAR_FILTER`,
   `EPD_PREFER_NAME_FIELD`) bleiben einzeln schaltbar und verhalten sich identisch.
3. **`EPD-Vertrag`** (`id`, `name`, `klassifizierung`, …) — keine Felder umbenennen. `matching_rules`
   liest nur diesen Vertrag, nie eine konkrete Datenquelle.
4. **Keine zirkulären Importe.** Abhängigkeitsrichtung strikt:
   `asphalt_glossar` (Blatt) ← `matching_rules` ← `epd_filter`. `asphalt_glossar` importiert
   **nicht** aus `matching_rules`.
5. **Identische Ergebnisse** auf dem Benchmark für P3 und P8 (siehe Regressionsschutz).

## Zielzustand — Schnittstelle

```python
# matching/matching_rules.py   (NEU — geteilte Fakten für Stage 3 + 5)
from dataclasses import dataclass
from typing import Dict, Any, Optional
from utils.asphalt_glossar import (
    parse_material_input,          # Stage 2 bleibt dort, wird nur importiert
    _ist_ausgeschlossen, _ist_generisch_asphalt,
    ASPHALT_TYPES,
)

# EINZIGE Quelle des Mismatch-Wissens (gezogen aus epd_filter.MATERIAL_MISMATCHES)
MATERIAL_MISMATCHES: Dict[str, list] = { ... }

@dataclass
class Bewertung:
    ist_asphalt: bool
    ausgeschlossen: Optional[str]        # gefundener Ausschluss-Begriff oder None
    schicht_passt: bool
    kategorie_konflikt: Optional[str]    # gefundener Mismatch-Begriff oder None

def bewerte_kandidat(material: Dict[str, Any], epd: Dict[str, Any]) -> Bewertung:
    """Die geteilten Fakten über ein (Material, EPD)-Paar. Keine Policy."""
    ...
```

Stage 3 und Stage 5 werden Aufrufer:

- **Stage 3** (`matching/epd_filter.py`, `EPDFilter`): pro EPD `bewerte_kandidat` aufrufen;
  `ausgeschlossen` → raus, `schicht_passt` → primär, sonst sekundär.
- **Stage 5** (`matching/epd_filter.py`, `ConfidenceValidator.validate_match`): dieselbe
  `Bewertung` lesen; `ausgeschlossen`/`kategorie_konflikt` → Cap auf
  `ValidationConfig.MAX_CONFIDENCE_EXCLUDED`; `schicht_passt == False` (bei
  `PREFER_NAME_FIELD`) → Cap auf 60 bzw. 35.

## Schritte

### Schritt 0 — Baseline einfrieren (Regressionsschutz)
- **Tun:** Benchmark-Lauf mit `EPD_DATA_SOURCE=local` für die Konfigurationen **P3**
  (`Filter` an, `Batch`/`NamePref` aus) und **P8** (alle an) ausführen; Output-JSONs (`id`,
  `id_confidence` je Schicht) als `before_P3.json` / `before_P8.json` sichern.
- **Akzeptanz:** Zwei Referenz-Outputs liegen vor. (Falls kein lauffähiger Benchmark verfügbar:
  einen kleinen Fixture-Lauf über `TestInput/...` sichern.)

### Schritt 1 — `matching/matching_rules.py` anlegen
- **Tun:** Neues Modul mit `Bewertung` + `bewerte_kandidat`. `MATERIAL_MISMATCHES` aus
  `epd_filter.py` **hierher verschieben** (dort entfernen). `bewerte_kandidat` berechnet die vier
  Fakten exakt wie heute:
  - `ausgeschlossen`: erster Begriff aus `AUSSCHLUSS_BEGRIFFE`, der in
    `f"{name} {klassifizierung}".lower()` vorkommt (Logik aus `_ist_ausgeschlossen`).
  - `ist_asphalt`: `_ist_generisch_asphalt(combined)` ODER ein Typ-Suchbegriff aus
    `ASPHALT_TYPES[material["typ"]]["suchbegriffe"]` trifft (Logik aus Stage-3 FALL 1).
  - `schicht_passt`: `material["schicht_epd_muss_enthalten"].lower() in combined`.
  - `kategorie_konflikt`: erster Begriff aus `MATERIAL_MISMATCHES[material_type]`, der trifft
    (Material-Typ-Ermittlung aus `ConfidenceValidator._get_material_type` hierher ziehen).
- **Tun:** Eigener `if __name__ == "__main__":`-Testblock im Stil von `epd_filter.py` /
  `local_store.py` (mehrere (Material, EPD)-Paare mit erwarteten Fakten, `assert`).
- **Akzeptanz:** `python matching/matching_rules.py` läuft, alle Asserts grün. Keine Importe aus
  `epd_filter` oder `prompt_builder`.

### Schritt 2 — Stage 5 auf `Bewertung` umstellen
- **Datei:** `matching/epd_filter.py`, `ConfidenceValidator`.
- **Tun:** In `validate_match` die vier Inline-Checks (Ausschluss-Loop, Material-Typ-Mismatch,
  Schicht-Check, Asphalt-Check) ersetzen durch **einen** Aufruf `bewerte_kandidat(parsed, epd)`
  und Interpretation der `Bewertung`. Die Cap-Schwellwerte (`MAX_CONFIDENCE_EXCLUDED`, 60, 35)
  bleiben unverändert. `_get_material_type` / `_ist_gleicher_material_typ` nach `matching_rules`
  ziehen oder von dort importieren. `MATERIAL_MISMATCHES`-Definition ist weg (jetzt in
  `matching_rules`).
- **Akzeptanz:** `validate_batch_results` und die Einzel-Validierung liefern für die Fixtures aus
  dem alten Testblock identische Caps/Begründungen.

### Schritt 3 — Stage 3 auf `Bewertung` umstellen
- **Datei:** `matching/epd_filter.py`, `EPDFilter` — und `utils/asphalt_glossar.py`,
  `filter_epds_for_material`.
- **Tun:** Im **Asphalt-Fall (FALL 1)** von `filter_epds_for_material` die Inline-Berechnung von
  Ausschluss/Asphalt/Schicht-Treffer durch `bewerte_kandidat` ersetzen (primär = `schicht_passt`,
  sekundär = sonst, raus = `ausgeschlossen`). **FALL 2 (Kategorie) und FALL 3 (unbekannt) bleiben
  strukturell**, nutzen aber `_ist_ausgeschlossen` aus dem geteilten Bestand — keine eigene
  Ausschluss-Logik mehr.
  > Hinweis: Falls eine zirkelfreie Platzierung schwerfällt, darf die Schleife komplett in
  > `EPDFilter` wandern und `filter_epds_for_material` zu einem dünnen Shim werden. Nicht die
  > Drei-Fall-Struktur neu erfinden.
- **Akzeptanz:** `EPDFilter.filter_for_materials` liefert für dieselben Eingaben dieselben
  `combined_epds` (gleiche IDs, gleiche primär/sekundär-Aufteilung).

### Schritt 4 — Regression verifizieren
- **Tun:** P3- und P8-Läufe aus Schritt 0 wiederholen → `after_P3.json` / `after_P8.json`.
- **Akzeptanz:** `before_*` und `after_*` sind **byte-identisch** in `id` und `id_confidence`.
  Bei Abweichung: Ursache finden (meist unterschiedliche Feld-Kombination — Filter nutzt
  `name + klassifizierung`, der alte Validator teils nur `klassifizierung`). Diskrepanz bewusst
  entscheiden und im PR dokumentieren, nicht stillschweigend ändern.

### Schritt 5 — Aufräumen & Doku
- **Tun:** Tote Importe entfernen. `prompt_builder.py` importiert `AUSSCHLUSS_BEGRIFFE` weiterhin
  aus `asphalt_glossar` (unverändert). `README.md` und `CONTEXT.md` ggf. minimal nachziehen, falls
  Symbole umgezogen sind.
- **Akzeptanz:** `python matching/matching_rules.py`, `python matching/epd_filter.py`,
  `python utils/asphalt_glossar.py` laufen alle grün.

## Was NICHT zu tun ist
- Stage 2 (`parse_material_input`) **nicht** verschieben.
- Confidence-Cap **nicht** zu einem Ablations-Schalter machen (bleibt konstant, Entscheidung des
  Teams).
- Die Drei-Fall-Filterstruktur (Asphalt / Kategorie / unbekannt) **nicht** umbauen.
- Keine neuen Felder am `EPD-Vertrag` oder `JSON-Vertrag`.
- Die Datenquellen-Naht (`datasources/`, ADR-0001) **nicht** anfassen.
