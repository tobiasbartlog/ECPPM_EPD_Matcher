# Analyse: Kontextfenster-Problem bei P1_Baseline und P2_Batch

## Hintergrund

Die Ablationsstudie testet 8 Konfigurationen (P1–P8) über drei binäre Faktoren:
- **BATCH_MODE** — ein LLM-Call für alle Schichten vs. N einzelne Calls
- **GLOSSAR_FILTER** — regelbasierte EPD-Vorfilterung (Stage 3) aktiv/inaktiv
- **PREFER_NAME_FIELD** — NAME-Feld vs. MATERIAL-Code als primärer Suchbegriff

P1_Baseline und P2_Batch haben `GLOSSAR_FILTER = false`. Das führt dazu, dass die
vollständige lokale EPD-Datenbank ungefiltert in den LLM-Prompt eingebettet wird.

---

## Messung: Lokale EPD-Datenbank

| Kennzahl | Wert |
|---|---|
| EPDs in `data/oekobaudat.db` | **5.720** |
| Gesamtzeichen (Kompakt-Modus, `{i}. {name} [{klassifizierung}]`) | **628.977** |
| Geschätzte Tokens (~4 Zeichen/Token) | **~157.000** |
| Geschätzte Tokens (~3 Zeichen/Token, Worst Case) | **~210.000** |

Der Kompakt-Modus listet pro EPD nur Index, Name und Klassifizierung — also die
kleinstmögliche Darstellung. Detail-Matching (`USE_DETAIL_MATCHING=true`) würde
technischeBeschreibung, Anmerkungen und Anwendungsgebiet ergänzen und die Token-Zahl
vervielfachen. Alle Messungen gelten für `USE_DETAIL_MATCHING=false` (BASE_ENV).

---

## Kontextfenster der eingesetzten Modelle

| Modell | Kontextfenster | EPD-Liste passt rein? |
|---|---|---|
| gpt-4o-mini | 128.000 Token | **Nein** (~157k–210k Token allein für EPDs) |
| gpt-5-nano | 32.000 Token | **Nein** |
| gpt-5-chat | 128.000 Token | **Nein** |
| gpt-5.2-chat | 128.000 Token | **Nein** |

Die EPD-Liste allein übersteigt bei allen vier Modellen das verfügbare Kontextfenster.
Hinzu kommen System-Prompt, Materialkontext, Glossar-Abschnitt und Aufgabenstellung,
die je nach Konfiguration weitere ~1.000–3.000 Token belegen.

---

## Technische Ursache im Code

```
azure_matcher.py, Zeile 38:
  if GlossarConfig.USE_GLOSSAR and FilterConfig.USE_GLOSSAR_FILTER:
      self._epd_filter = EPDFilter(...)   # Filter aktiv

# Bei USE_GLOSSAR_FILTER=false:
azure_matcher.py, Zeile 87–89:
  else:
      filtered_epds = epds                # ALLE 5.720 EPDs weitergegeben
      print(f"[Stage 3] Übersprungen - Verwende {len(filtered_epds)} EPDs")

prompt_builder.py, Zeile 162–168:
  for i, epd in enumerate(epds, 1):      # Keine Trunkierung
      entries.append(f"{i}. {name} [{klassifizierung}]")
```

Es gibt keinen Fallback, der die EPD-Liste bei Kontextüberschreitung automatisch kürzt.

---

## Verhalten bei Kontextüberschreitung

Die Azure OpenAI API reagiert auf zu lange Prompts auf zwei Arten:

**Fall A — API-Fehler (400 Bad Request):**
Der Call wird abgelehnt, `benchmark_alltests.py` fängt die Exception und markiert
den Run als Fehler (`error_count += 1`). Das Ergebnis ist im Report sichtbar.

**Fall B — Stilles Abschneiden (silent truncation):**
Ältere oder bestimmte Deployment-Konfigurationen schneiden den Prompt ohne Fehlermeldung
ab. Der LLM sieht dann nur einen zufälligen Vorderteil der EPD-Liste (z.B. EPD 1–3.000),
ohne dass dies im Output kenntlich gemacht wird. Das Matching-Ergebnis ist in diesem Fall
**systematisch verzerrt** zugunsten von EPDs mit kleinem Index (alphabetisch frühe Namen).

---

## Auswirkung auf die Ablationsstudie

Die Konfigurationen P1 und P2 sind **nicht als valide Baseline-Runs interpretierbar**,
solange die lokale Datenbank mehr EPDs enthält als in das Kontextfenster der Modelle passen.

Konkret betroffene Konfigurationen:

| Config | BATCH | FILTER | NAME | Status |
|---|---|---|---|---|
| P1_Baseline | - | - | - | **Nicht valide** |
| P2_Batch | x | - | - | **Nicht valide** |
| P3_Filter | - | x | - | Valide (Filter reduziert auf ~50–150 EPDs) |
| P4_NamePref | - | - | x | **Nicht valide** |
| P5_BatchName | x | - | x | **Nicht valide** |
| P6_FilterName | - | x | x | Valide |
| P7_BatchFilter | x | x | - | Valide |
| P8_All | x | x | x | Valide |

Auch P4_NamePref und P5_BatchName sind betroffen — das Problem ist nicht auf "kein Filter"
beschränkt, sondern trifft alle Konfigurationen ohne `GLOSSAR_FILTER=true`.

---

## Handlungsoptionen für das Paper

### Option A — P1/P2/P4/P5 aus dem Benchmark ausschließen (empfohlen)
Den Benchmark auf die vier Filter-Konfigurationen (P3, P6, P7, P8) reduzieren.
Im Paper explizit begründen: ohne Vorfilterung überschreitet die EPD-Datenbank
(5.720 EPDs, ~157k Token im Kompakt-Modus) das Kontextfenster aller getesteten Modelle.
Die Frage der Ablation verschiebt sich dann auf: *Welche Kombination aus BATCH_MODE
und PREFER_NAME_FIELD wirkt sich innerhalb des gefilterten Kandidatensets am stärksten aus?*

### Option B — Kontrolliertes EPD-Cap für P1/P2/P4/P5
Für die No-Filter-Konfigurationen ein hartes EPD-Limit einführen (z.B. die 500 häufigsten
oder zufällig gezogene 500 EPDs). Dadurch wird P1 zu einer "unkontrollierten Zufalls-Baseline"
— methodisch schwächer, aber zumindest reproduzierbar. Im Paper transparent ausweisen.

### Option C — Modell mit großem Kontextfenster
Einen separaten Run mit einem Modell mit ≥ 256k Token Kontextfenster durchführen
(z.B. GPT-4o mit 256k oder Gemini 1.5 Pro mit 1M). Damit wäre ein echter
"kein Filter"-Vergleich möglich, jedoch nur für dieses eine Modell — was die
Vergleichbarkeit mit den anderen Modellen einschränkt.

---

## Empfehlung

**Option A** ist für ein Paper am saubersten. Die Vorfilterung (Stage 3) ist kein
optionales Feature, sondern eine technische Notwendigkeit bei der gegebenen Datenbankgröße.
Die Ablationsstudie sollte das so darstellen: der GLOSSAR_FILTER ist eine **Voraussetzung**
für funktionsfähige Runs, nicht eine von drei gleichrangigen Variablen.

Die eigentliche Forschungsfrage lautet dann:
*Welchen Effekt haben BATCH_MODE und PREFER_NAME_FIELD auf Matching-Qualität und Kosten,
gegeben dass der GLOSSAR_FILTER immer aktiv ist?*

Das reduziert die Studie von 2³ = 8 auf 2² = 4 Konfigurationen (P3, P6, P7, P8) —
methodisch klarer und ehrlicher.
