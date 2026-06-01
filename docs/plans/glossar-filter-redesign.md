# Plan — Glossar-Filter: Funktionsbeschreibung & Präzisions-Redesign

> **Zweck dieses Dokuments:** Zweiteilig. **Teil A** beschreibt präzise, *was die einzelnen
> Filter heute tun und wie ihre Logik aufgebaut ist* — direkt verwendbar für den Methodenteil
> des Papers. **Teil B** hält den Präzisions-Redesign als Soll-Zustand fest (umgesetzt,
> Ergebnis einer Design-Session, siehe Entscheidungen). Vokabular nach `CONTEXT.md`
> (`Glossar-Filter`, [[matching-rules]], `Bewertung`, `Confidence-Cap`, `Schicht-Taxonomie`,
> `EPD-Vertrag`, `Klassifizierung`).

## Domänen-Kontext (Voraussetzung für jede Filter-Entscheidung)

Der Matcher arbeitet im **Tiefbau**. Die beobachteten Eingaben (`JSON-Vertrag`, alle Läufe in
`TestInput/`) sind reiner Straßenoberbau gemäß `Schicht-Taxonomie`:

| Schicht (`NAME`) | Material (`MATERIAL`) | Materialklasse |
|---|---|---|
| Deckschicht | SMA 8 S (PmB) | Asphalt |
| Binderschicht | AC 16 B S SG (PmB) | Asphalt |
| Tragschicht | AC 32 T S mit Straßenbaubitumen 30/45 | Asphalt |
| Schottertrag | AC 32 T S … | Asphalt / ungebunden |
| Frostschutzschicht | Gesteinskörnungsgemisch 0/32 | ungebunden mineralisch |

Der deklarierte Scope ist etwas breiter (Beton-Fahrbahndecken, Bordsteine/Pflaster, Rohre,
Geotextilien, Bitumenemulsion als eigene Schicht), aber **kein Hochbau** und **keine Dämmung**.
Konsequenz: neue Materialklassen werden **on-demand** mit echten Beispiel-Eingaben ergänzt, nicht
spekulativ. Details: [[domain-scope-tiefbau]].

---

# Teil A — Funktionsbeschreibung der Filter (Ist-Zustand)

Die Vorfilterung lebt in zwei `5-Stage-Pipeline`-Stufen, die beide dieselben Fakten aus
[[matching-rules]] lesen:

- **Stage 3 — `Glossar-Filter`** (`matching/epd_filter.py`, `EPDFilter`): reduziert den
  vollen `EPD-Vertrag`-Katalog (lokal 5.720 Datensätze) auf relevante Kandidaten, **bevor**
  der Prompt gebaut wird.
- **Stage 5 — `Confidence-Cap`** (`matching/epd_filter.py`, `ConfidenceValidator`): korrigiert
  die LLM-Confidence regelbasiert nach unten.

## A.1 Die geteilten Fakten: `bewerte_kandidat → Bewertung`

`matching/matching_rules.py` berechnet pro (Material, EPD)-Paar **einmal** vier Fakten (keine
Policy). Grundlage ist stets `combined = f"{name} {klassifizierung}".lower()` aus dem
`EPD-Vertrag`.

| Faktum | Bedeutung | Heutige Berechnung |
|---|---|---|
| `ausgeschlossen` | erster `AUSSCHLUSS_BEGRIFFE`-Treffer oder `None` | Substring in `combined` |
| `ist_asphalt` | EPD hat Asphalt-Bezug | `_ist_generisch_asphalt(combined)` **oder** ein Typ-Suchbegriff aus `ASPHALT_TYPES[typ]` trifft in `combined` |
| `schicht_passt` | `schicht_epd_muss_enthalten` (z.B. „Deck") steckt im EPD | Substring in `combined` |
| `kategorie_konflikt` | erster `MATERIAL_MISMATCHES[material_typ]`-Treffer oder `None` | Substring in `combined` |

Der Material-Typ für den Mismatch (`asphalt` / `schotter` / `daemmung`) wird aus dem geparsten
Material abgeleitet (`get_material_type`).

## A.2 Stage 3 — Glossar-Filter: Drei-Fall-Struktur

Stage 2 (`parse_material_input`) liefert das geparste Material; daraus wählt der Filter **genau
einen** von drei Fällen:

### FALL 1 — Asphalt  (`parsed["ist_asphalt"] == True`)
Pro EPD wird `bewerte_kandidat` gelesen und als Tor interpretiert:

1. `ausgeschlossen` gesetzt → **raus**
2. `ist_asphalt == False` (EPD selbst hat keinen Asphalt-Bezug) → **raus**
3. `schicht_passt == True` → **primär**
4. sonst → **sekundär**

> **Aktuelle Lücke:** `kategorie_konflikt` wird in FALL 1 **nicht** ausgewertet. Eine Bitumenbahn
> erhält über das generische `"bitumen"` ein `ist_asphalt == True` und passiert daher als sekundär.

### FALL 2 — Nicht-Asphalt-Kategorie
Greift, wenn `_detect_material_category(material, schicht)` eine Kategorie aus
`MATERIAL_KATEGORIEN` (`schotter`, `frostschutz`, `abdichtung`) liefert. Pro EPD gegen `combined`:

1. globaler Ausschluss (`AUSSCHLUSS_BEGRIFFE`) → raus
2. kategorie-eigener Ausschluss (z.B. schotter schließt `asphalt`, `beton`, … aus) → raus
3. Kategorie-Suchbegriff trifft → **primär**
4. Fallback: liegen < 10 Primär-Treffer vor, werden EPDs, deren `name` ein Material-Wort enthält,
   als **sekundär** ergänzt

### FALL 3 — Unbekannt
Greift, wenn weder Asphalt noch eine bekannte Kategorie erkannt wurde. Aus `material + schicht`
werden Schlüsselwörter (> 2 Zeichen, ohne Stoppwörter) gebildet und als Substring gegen `combined`
gesucht; globaler Ausschluss greift vorab. Treffer → **primär**, keine sekundär-Ebene.

### Zusammenführung & Reihenfolge
Über alle Materialien werden die Kandidaten **primär-zuerst, dann sekundär, dedupliziert** zu
`combined_epds` zusammengeführt — das ist exakt die Reihenfolge, in der die EPDs in den Prompt
gehen. `MAX_EPD_IN_PROMPT` ist nur eine **Token-Sicherheitsgrenze** (kein Relevanzfilter); durch
die primär-zuerst-Ordnung verwirft ein etwaiges Kürzen nie einen Primär-Treffer.

## A.3 Stage 5 — Confidence-Cap

Liest dieselbe `Bewertung` und kappt die vom LLM gelieferte Confidence:

| Bedingung | Cap |
|---|---|
| `ausgeschlossen` gesetzt | `MAX_CONFIDENCE_EXCLUDED` (20) |
| `kategorie_konflikt` gesetzt | 20 |
| `schicht_passt == False` (nur bei `PREFER_NAME_FIELD`) | 60 (Asphalt) bzw. 35 |
| Material ist Asphalt, EPD aber nicht | 35 |

Ergebnisse unter `MIN_CONFIDENCE` (25) werden verworfen. Der `Confidence-Cap` ist bewusst
**konstant** über alle `Ablations-Schalter`-Konfigurationen.

## A.4 Gemessene Schwächen (empirisch, via `tools/filter_trace.py` gegen die lokale DB)

Diese Zahlen eignen sich direkt als empirischer Befund im Paper:

| Szenario | Zweig | Treffer | Befund |
|---|---|---|---|
| `AC 16 D S` / Deckschicht | FALL 1 | 57 | **27 davon** sind Bitumenbahnen/-Emulsionen (Hochbau-Abdichtung) — ~47 % Rauschen, da `"bitumen"` generisch als Asphalt zählt und FALL 1 den `kategorie_konflikt` ignoriert |
| `Schotter 0/45` / Schottertrag | FALL 2 | 507 | **473 davon** nur über den Suchbegriff `"mineral"`, der „**Mineral**ische Baustoffe" in der `Klassifizierung` trifft → ganzer Katalogast statt Schotter; nur ~34 echte Granulat-Treffer |
| `Holzfenster` / Fassade | FALL 3 | 930 | **897 davon** nur über `"fassade"` (trifft „Vorhang**fassade**n") |

**Kernursache (gilt für alle drei Fälle):** Positive Suchbegriffe werden als **Substring gegen
`name + klassifizierung`** geprüft. Die `Klassifizierung` enthält breite deutsche Oberbegriffe;
ein generisches Wort trifft daher einen ganzen Katalogast. Wortgrenzen (`\b`) lösen das **nicht**
(`"mineral"` steht an einer echten Wortgrenze in „Mineralische").

---

# Teil B — Präzisions-Redesign (Soll-Zustand)

## B.1 Leitprinzipien

1. **Asymmetrie: streng rein, breit raus.** Positive Suchbegriffe (Inklusion) werden nur gegen
   den **`name`** geprüft und auf spezifische Begriffe beschränkt. Ausschluss- und
   Mismatch-Begriffe (Exklusion) prüfen weiter gegen `name + klassifizierung` — einen ganzen
   „Dämmstoffe"-Ast auszuschließen, wenn man Schotter sucht, ist erwünscht.
2. **Kontextabhängiger Konflikt statt globalem Verbot.** Ob ein Material „Rauschen" ist, hängt
   vom Eingabe-Material ab. Eine Emulsions-EPD ist ein gültiges *Material*, aber für eine
   Asphaltschicht-Eingabe ein Fehltreffer.
3. **On-demand statt spekulativ.** Neue Materialklassen werden erst mit echten Beispiel-Eingaben
   und getesteten Suchbegriffen ergänzt.
4. **Ein wirksamer Hebel bei entferntem Token-Cap.** Da `MAX_EPD_IN_PROMPT` praktisch deaktiviert
   ist, gehen primär und sekundär gleichermaßen an das LLM. „Abwerten" reduziert das Prompt-Rauschen
   also nicht — nur **Verwerfen** in Stage 3 wirkt.

## B.2 Entschiedene Änderungen

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | **`kategorie_konflikt` in Stage 3 (FALL 1 + FALL 2) verwerfen** (wie `ausgeschlossen`) | Für eine Asphaltschicht ist eine Bitumenbahn nie korrekt; ohne Cap ist Verwerfen der einzige wirksame Hebel. Entfernt ~47 % Rauschen aus dem Asphalt-Kandidatenset |
| 2 | **Inklusion gegen `name`** (nicht `combined`); FALL 2/FALL 3 | Verhindert Treffer auf Oberbegriffe der `Klassifizierung` (`"mineral"`, `"fassade"`) |
| 3 | **Generische Suchbegriffe streichen** in `MATERIAL_KATEGORIEN`: `mineral`, `mineralgemisch`, `sand`, `gestein`, `naturstein`; **behalten**: `schotter`, `kies`, `splitt`, `edelsplitt`, `brechsand`, `gesteinskörnung`, `rundkies`, `kiessand`, `frostschutz` | Spezifische Begriffe stehen real im `name` (z.B. „Gesteinskörnung 0/32") — Recall bleibt erhalten |
| 4 | **`daemmung` vollständig tilgen** (`MATERIAL_MISMATCHES`-Key + `get_material_type`-Zweig; Kategorie bereits entfernt) | Kein Hochbau, keine Dämmung — toter Code und Fehlmatch-Vektor |
| 5 | **`emulsion` als Konflikt behalten** in `MATERIAL_MISMATCHES["asphalt"]`/`["schotter"]` | Emulsion ist valides Tiefbau-Material, aber kein gültiger Treffer für eine Asphalt-/Granulatschicht. Wird erst eigene Kategorie, wenn eine Emulsions-Schicht als Eingabe kommt |
| 6 | **`abdichtung` bleibt eigene Kategorie**, „bahn"-Produkte nur Konflikt gegen Asphalt/Schotter/Frostschutz | Brückenabdichtung (bituminöse Dichtungsbahn) ist realer Tiefbau |
| 7 | **Globale Ausschlussliste**: Beton/Pflaster/Festigkeitsklassen bleiben **entfernt**; Test anpassen | Beton-Fahrbahndecken & Pflaster sind potenziell valide Tiefbau-Materialien — dürfen nicht global ausgeschlossen werden |

## B.3 Implementierungsschritte (pro Datei)

> Reihenfolge nach Hebelwirkung. Nach jedem Schritt `tools/filter_trace.py` (fixtures **und** db)
> neu erzeugen und gegen die gemessenen Erwartungen prüfen.

### Schritt 0 — Baseline einfrieren
- `python -m tools.filter_trace --source db` ausführen, Lauf als Referenz sichern (Vorher-Zahlen
  je Szenario: 57 / 507 / 930 …).

### Schritt 1 — `matching/matching_rules.py`
- `MATERIAL_MISMATCHES`: `"daemmung"`-Key entfernen; `"emulsion"` in `asphalt`/`schotter` **behalten**.
- `get_material_type`: `daemmung`-Zweig (xps/eps/pur/mineralwolle) entfernen.
- `bewerte_kandidat`: **Inklusion** (`ist_asphalt`, Typ-Suchbegriffe) gegen `name` statt `combined`;
  **`ausgeschlossen` und `kategorie_konflikt` weiter gegen `combined`** (Asymmetrie, Prinzip B.1.1).
- Testblock: Betonpflaster-Fall umschreiben — prüft künftig, dass Beton/Pflaster bei
  Asphalt-Eingabe über `ist_asphalt == False` rausfällt (nicht über globalen Ausschluss).
- **Akzeptanz:** `python -m matching.matching_rules` grün.

### Schritt 2 — `utils/asphalt_glossar.py`
- `MATERIAL_KATEGORIEN["schotter"|"frostschutz"].suchbegriffe`: generische Begriffe streichen (B.2 #3).
- `abdichtung` unverändert lassen.

### Schritt 3 — `matching/epd_filter.py` (Stage 3)
- **FALL 1:** nach `bewerte_kandidat` zusätzlich `if b.kategorie_konflikt: continue` (verwerfen).
- **FALL 2:** ebenfalls `kategorie_konflikt` verwerfen; Inklusion (Suchbegriff-Treffer) gegen `name`.
- **FALL 3:** Schlüsselwort-Suche gegen `name` statt `combined`; globaler Ausschluss weiter gegen `combined`.
- Die Drei-Fall-Struktur bleibt erhalten.
- **Akzeptanz:** `python -m matching.epd_filter` grün; Trace-Zahlen ~ Asphalt 57→~30, Schotter 507→~40.

### Schritt 4 — Recall-Kontrolle
- Trace gegen die DB: sicherstellen, dass „Gesteinskörnung 0/32"-artige Datensätze (spezifischer
  Begriff im `name`) erhalten bleiben. Bei Recall-Verlust Suchbegriff-Liste nachschärfen.

### Schritt 5 — Doku nachziehen
- `CONTEXT.md` → Definition **Glossar-Filter**: der Satz „sucht deutsche Substrings … in
  `name + klassifizierung`" wird zur **Asymmetrie** präzisiert (Inklusion gegen `name`,
  Exklusion gegen `name + klassifizierung`).
- `README.md`/`CLAUDE.md`: Stage-3-Beschreibung minimal anpassen.

## B.4 Erwartete Wirkung

| Szenario | vorher | nachher (erwartet) |
|---|---|---|
| Asphalt-Kandidaten (AC 16 D S) | 57 (47 % Rauschen) | ~30 (Bitumenbahn/Emulsion verworfen) |
| Schotter | 507 (~7 % echt) | ~30–40 |
| toter `daemmung`-Code | vorhanden | entfernt, Test grün |

## B.5 Was NICHT zu tun ist
- Stage 2 (`parse_material_input`) nicht anfassen — die `name`-vs-`combined`-Umstellung betrifft
  nur die **Filter-Inklusion**, nicht den Parser.
- Den `Confidence-Cap` (Stage 5) nicht zu einem `Ablations-Schalter` machen — bleibt konstant.
  Stage 5 wird durch Schritt 3 weitgehend redundant für Konflikte (sie sind dann schon raus),
  bleibt aber als Sicherheitsnetz für Grenzfälle.
- Keine spekulativen Kategorien (Beton/Pflaster/Rohre/Geotextil) anlegen — on-demand (B.1.3).
- Die Datenquellen-Naht (`datasources/`) und den `EPD-Vertrag` nicht verändern.
