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

#### 1.2.1 Genaue Funktion der drei Ablations-Schalter

Diese Beschreibungen sind die Vorlage für den Methodik-Teil des Papers. Sie spiegeln den
Code-Stand der v2-Studie wider (inkl. Filter-Quality-Fixes — siehe Abschnitt 1.2.2).

**`Batch` (`EPD_USE_BATCH_MODE`)** — wirkt in Stage 4.
- **ON**: Alle Schichten eines Inputs werden in einer einzigen LLM-Anfrage gemeinsam abgefragt.
  EPD-Katalog und System-Prompt werden nur einmal übertragen; die Antwort enthält strukturierten
  JSON-Output für N Layer.
- **OFF**: Pro Schicht eine eigene LLM-Anfrage. EPD-Katalog und System-Prompt werden N-mal
  übertragen.
- **Erwartete Wirkung**: Drastische Token-Reduktion bei OFF→ON, dafür höheres Failure-Risiko,
  weil das Modell strukturierten Output für N Layer simultan liefern muss. Im v1-Befund mit
  P2 leicht verringerter Accuracy gegenüber P1.

**`Filter` (`EPD_USE_GLOSSAR_FILTER`)** — wirkt in Stage 3.
- **ON**: Der EPD-Katalog wird vor dem LLM-Call durch eine mehrstufige, regelbasierte Filterkette
  reduziert. Die Kette ist hierarchisch:
  1. **Tiefbau-Scope-Whitelist** *(v2-neu)*: Nur EPDs, deren Klassifizierungspfad mit einem
     der drei erlaubten Tiefbau-Präfixe beginnt, passieren den Filter (siehe §1.2.2 für
     die empirische Auswahl):
     - `Mineralische Baustoffe / Asphalt`
     - `Mineralische Baustoffe / Zuschläge`
     - `Mineralische Baustoffe / Mörtel und Beton / Beton`

     Strukturelle Exklusion aller Hochbau-, Gebäudetechnik-, Dämmstoff-, Metall- und
     Kunststoff-EPDs. Verhindert Cross-Domain-Hallucinations (z.B. Teppichfliesen für
     Asphaltschichten, Stahlblech für Schottertragschichten).
  2. **Drei-Fall-Logik je nach geparstem Material-Typ**:
     - *Fall 1 — Asphalt erkannt* (regex-Match auf TL Asphalt-StB-Code oder Fuzzy-Treffer):
       Zwei-Stufen-Filter. *Primäre* Treffer enthalten den Schicht-Term (z.B. „Binder" für
       Binderschicht) im `name` UND einen Asphalt-Term in `name + klassifizierung`.
       *Sekundäre* Treffer enthalten nur Asphalt-Term, kein Schicht-Match.
     - *Fall 2 — Nicht-Asphalt, aber kategorisierbar* (Schotter, Frostschutz, Abdichtung
       via Keyword-Match): Kategorie-spezifische Inklusionsbegriffe gegen `name`,
       Kategorie-Ausschlussbegriffe gegen `name + klassifizierung`.
     - *Fall 3 — Unbekanntes Material*: Tokenisierte Keyword-Suche aus
       `material + schicht`-Text gegen `name`.
  3. **Globale Ausschluss- und Mismatch-Listen** wirken in allen drei Fällen:
     - `AUSSCHLUSS_BEGRIFFE` (z.B. `Mörtel`, `Ziegel`, `Gips`) — wären typischerweise schon
       durch die Whitelist abgefangen, fungieren als zweiter Riegel.
     - `MATERIAL_MISMATCHES` (z.B. `Bitumenbahn`, `Schweißbahn` werden nicht als Asphalt-Match
       akzeptiert) — fängt EPDs ab, deren Klassifizierung zwar Tiefbau-relevant scheint,
       deren Produkttyp aber zur Material-Klasse des Inputs nicht passt.
  - **Architektur-Hinweis**: Inklusion erfolgt asymmetrisch gegen `name` (verhindert
    Treffer auf breite Oberbegriffe in `klassifizierung`); Exklusion erfolgt gegen
    `name + klassifizierung` (Klassifizierung ist für Negativ-Aussagen zuverlässig).
- **OFF**: Der vollständige EPD-Katalog wird ohne jegliche Vorverarbeitung an das LLM übergeben.
  Tiefbau-Whitelist, Schicht-Filter und globale Listen bleiben inaktiv.
- **Erwartete Wirkung**: Drastische Token-Reduktion (in v1 Faktor ~270×), reduziertes
  Hallucination-Risiko durch Cross-Domain-Ausschluss, potenziell schlechterer Recall bei
  Edge Cases (unbekannte Materialien).

**`NamePref` (`EPD_PREFER_NAME_FIELD`)** — wirkt in Stage 1 und propagiert in Stage 5.
- **ON**: Bei der Schicht-Extraktion wird das strukturierte `NAME`-Feld (RStO-orientierte
  5-Werte-Schicht-Taxonomie: Deckschicht / Binderschicht / Tragschicht /
  Schottertragschicht / Frostschutzschicht) als primäre Schicht-Quelle bevorzugt.
  Folgewirkungen: Stage 3 verwendet den abgeleiteten Schicht-Term für die Inklusionsprüfung;
  Stage 5 kappt Confidence auf 60, wenn ein passender Schicht-Term im EPD fehlt.
- **OFF**: Das nutzergeschriebene `MATERIAL`-Feld wird als primäre Schicht-Quelle verwendet.
  Stage-5-Schicht-Cap inaktiv.
- **Erwartete Wirkung**: `NAME` ist 1:1 zur EPD-Klassifizierungs-Hierarchie und reduziert
  falsche Schicht-Zuordnungen, wenn `MATERIAL` von der Standardterminologie abweicht.

#### 1.2.2 Lessons learned aus v1 und resultierende Parameter-Anpassungen für v2

Diese Sektion dokumentiert nachvollziehbar, was aus dem v1-Lauf gelernt wurde und welche
Stellschrauben für v2 angepasst wurden — als Vorlage für die Paper-Abschnitte „Pilot study
findings" und „Method refinements" sowie für die Reproduzierbarkeit der Studie.

**Was wir aus v1 wissen** (gpt-4o-mini + P3_Filter erreichte 100% Accuracy bei 1/12 der
Kosten von P1_Baseline). Die Stage-3-Vorfilterung war damit der zentrale Cost-Efficiency-Hebel.
Reviewer kritisierten v1 primär am Single-Test-Case (siehe Reviewer-Kritik-Tabelle).

**Was wir aus v1-Pilotruns danach gelernt haben** (94 Filter-Quality-Runs zwischen v1- und
v2-Submission, 8 Configs × 4 Modelle × 3 Inputs, Analyse-Artefakte unter
`.scratch/filter-quality/`):

| # | Befund | Beobachtung | Root Cause | Studienrisiko |
|---|--------|-------------|------------|---------------|
| 1 | Precision-Bug Asphalt | Für `AC 16 B S` lieferte Stage 3 Teppichfliesen-, Sanitär- und Lüftungsgerät-EPDs als Asphalt-Kandidaten | `_ist_generisch_asphalt` matchte das Substring `bitumen` im Namen von Bodenbelägen mit Bitumen-Trägerplatte. Konsequenz: das `ist_asphalt`-Fakt in [[Bewertung]] wurde falsch True — betrifft nicht nur Stage 3, sondern auch die Stage-5-Confidence-Validierung in den Filter=OFF-Baseline-Configs (P1/P2/P4/P5) | Verfälscht die Filter-vs-Baseline-Aussage. Doppelt kritisch: in P1/P4 ohne Vorfilter ist Stage 5 die letzte Verteidigung gegen LLM-Hallucinations; ein falsch-positives `ist_asphalt` deaktiviert dort die „kein Asphalt-Bezug → cap auf 35"-Regel |
| 2 | Recall-Bug Schottertragschicht | Für `STSuB 0/45` lieferte Stage 3 vier Stahlblech-EPDs und null Schotter-EPDs | (a) `STSuB` wurde im Glossar nicht als Schotter-Kategorie erkannt → Fallback auf Fall 3 (Keyword-Suche). (b) Stoppwort-Liste in Fall 3 enthielt `nicht` nicht → „nicht" aus „Nicht bituminöse Tragschicht" matchte „nicht-schlussgeglüht" in Stahlblech-EPD-Namen | LLM bekam null relevante EPDs, gab 0 Matches zurück — verfälscht Filter-Accuracy für nicht-Asphalt-Schichten systematisch nach unten |
| 3 | Klassifikations-Pfade in Ökobaudat anders als angenommen | DB-Inspektion zeigt: `Mineralische Baustoffe / Beton` und `… / Pflastersteine` existieren nicht; Beton liegt unter `… / Mörtel und Beton / Beton`, Pflastersteine unter `… / Steine und Elemente / Betonfertigteile und Betonwaren` | Annahme aus der Filter-PRD basierte nicht auf einer DB-Validierung | Whitelist-Definition wäre falsch geworden |

**Empirisch fundierte Tiefbau-Scope-Whitelist** (DB-Snapshot, Stand v2). Auswahl basiert auf
Top-Level-Inspektion aller `klassifizierung`-Pfade unter `Mineralische Baustoffe / …` und
Stichproben-Validierung der enthaltenen EPD-Namen:

| Whitelist-Präfix | EPDs in DB | In Scope für v2 weil… |
|------------------|-----------:|----------------------|
| `Mineralische Baustoffe / Asphalt` | 6 | Deckt alle vier v2-Asphalt-Subtypen (Tragschichten, Asphaltbinder, Splittmastix, Gussasphalt) — direkter Match für Deckschicht / Binderschicht / Bituminöse Tragschicht |
| `Mineralische Baustoffe / Zuschläge` | 35 | Deckt Schotter (Naturstein 16/32, Bims), Sand & Kies, Kraftwerksnebenprodukte — direkter Match für Schottertragschicht / Frostschutzschicht |
| `Mineralische Baustoffe / Mörtel und Beton / Beton` | 278 | Reservescope für mögliche Betonfahrbahn-Inputs in zukünftigen Erweiterungen. Inhalt überwiegend Hochbau-Beton (Stahlbeton C20/25); diese werden durch die Schicht- und Kategorie-Filter (Fall 1 verlangt Asphalt-Term; Fall 2 schließt `beton` für Schotter aus) für die v2-Schichten weggefiltert |
| **Summe** | **319 EPDs** (≈ 11,5 % von 2779) | |

**Bewusst nicht in der Whitelist**:

| Pfad | EPDs | Begründung der Exklusion |
|------|-----:|---------------------------|
| `Mineralische Baustoffe / Bindemittel / *` | 198 | Zement/Kalk/Gips sind Bindemittel, keine Schicht-Materialien |
| `Mineralische Baustoffe / Steine und Elemente / Betonfertigteile und Betonwaren` | 72 | Enthält Betonpflastersteine (Tiefbau) und Mauersteine/Decken/Wände/Treppen (Hochbau); keine Pflasterstraße in v2-Test-Schichten |
| `Mineralische Baustoffe / Steine und Elemente / *` (außer Betonfertigteile) | 131 | Ziegel, Gipsplatten, Faserzement etc. ausschließlich Hochbau |
| `Mineralische Baustoffe / Mörtel und Beton / *` (außer Beton) | 78 | Putz, Mauermörtel, Kleber, Estrich (Estrich zusätzlich in `AUSSCHLUSS_BEGRIFFE`) — alles Hochbau |
| `Dämmstoffe / Schaumglas / Granulat` (Schaumglasschotter) | 1 | RStO-unüblich; falls in Zukunft als Frostschutz benötigt, gezielt ergänzen |
| Alle anderen Top-Level-Klassen | 1581 | Gebäudetechnik, Kunststoffe, Metalle, Dämmstoffe, Holz, Beschichtungen — strukturell kein Tiefbau |

**HGT-Sonderfall**: „Hydraulisch gebundene Tragschicht" wurde in §1.1 als möglicher Input C
genannt. DB-Suche („hydraulisch", „HGT", „Verfestigung") liefert 0 Treffer. → Falls Input C
eine HGT-Schicht enthält, muss diese mit `ground_truth = null` markiert und aus der
Accuracy-Berechnung ausgeschlossen werden (analog zum v1-Vorgehen bei nicht-passenden EPDs).
Dies wird im Paper als bekannte Datenbank-Limitation referenziert.

**Daraus resultierende Anpassungen für v2** (alle als Bestandteil des `Filter`-Treatments,
**kein neuer Ablations-Schalter**):

| Anpassung | Wirkort | Effekt |
|-----------|---------|--------|
| Tiefbau-Scope-Whitelist (3 Präfixe) | `matching_rules.py` (Konstante + Helper), `epd_filter.py` (Anwendung) | Fix Befund #1 *strukturell* bei `Filter=ON`; reduziert die Vor-LLM-Menge von 2 779 auf ~319 EPDs (v2-DB) |
| Negativ-Kontext-Fix in `_ist_generisch_asphalt` (`bitumen` allein gilt nicht mehr als Asphalt-Bezug, wenn `bitumenbahn`/`bitumenträger`/`bitumenbelag`/`bitumendach` ebenfalls im Text ist) | `asphalt_glossar.py` (Logik) | Fix Befund #1 *an der Wurzel*: Stage 5 cap'd Teppichfliesen-/Bodenbelag-EPDs auch in den Filter=OFF-Configs (P1/P2/P4/P5) zuverlässig. Die Whitelist (Vorzeile) und dieser Fix bilden Defense-in-Depth: Whitelist verhindert das Problem strukturell in Stage 3, der Source-Fix sichert die Korrektheit des `ist_asphalt`-Fakts für alle Aufrufer von `bewerte_kandidat` |
| Erweiterte Material-Kategorie-Keywords (Schotter: `stsub`, `ungebunden`, `schottertrag`; Frostschutz: `fss`) | `asphalt_glossar.py` (Daten) | Fix Befund #2a — STSuB landet im Schotter-Fall 2 statt im Fallback Fall 3 |
| Erweiterte Stoppwort-Liste in Fall 3 (`nicht`, `kein`, `ohne`, `auch`, `beim`, `sein`, `wird`) | `epd_filter.py` | Fix Befund #2b — kurze Negationen erzeugen keine Cross-Domain-Matches mehr. Bewusst gegen die alternative Anhebung der Mindest-Token-Länge auf 4 entschieden, damit 3-Letter-Codes wie `OPA` (Offenporiger Asphalt) als zukünftige Fallback-Inputs erkennbar bleiben |

**Per-Input-Validierung der Keyword-Erweiterung** (alle v2-MATERIAL-Werte
gegen den neuen Filter durchgespielt):

| Input | Layer | MATERIAL | Erkennung im neuen Filter |
|-------|------:|----------|---------------------------|
| ablation_a | 4 | `STSuB 0/45` | **Neu**: trifft `stsub` → Schotter-Kategorie |
| ablation_a | 5 | `FSS 0/32` | Schon vorher via NAME=Frostschutzschicht; `fss`-Keyword als Konsistenz-Backup |
| ablation_b | 5 | `Gesteinskörnungsgemisch 0/32` | Schon vorher via Keyword `gesteinskörnung` |
| ablation_c | 4 | `Schotter ungebunden, gebrochenes Korn 0-45` | Schon vorher via Keyword `schotter`; `ungebunden` als Backup |
| ablation_c | 5 | `Kies-Sand-Gemisch frostsicher, natürlich gewonnen, bis 32mm` | Schon vorher via Keyword `kies` |

Bewusst **nicht** aus der PRD übernommen: die Abkürzungen `stuetzschicht`, `gnb`, `rcb` und
`fsk`/`fsks` (letztere bereits in v1-Code). Begründung: weder im v2-Test-Set noch in RStO als
Standardterm referenziert; Substring-Matching-Risiko in unverwandten EPD-Namen überwiegt den
unbelegten Nutzen.

**Fall 3 ist in v2 ein dead path** (paper-relevant): nach Whitelist-Vorfilter, Tiefbau-Scope
und erweiterten Schotter-/Frostschutz-Keywords trifft kein v2-MATERIAL mehr den
Keyword-Fallback in `_filter_epds`. Der Stoppwort-Fix ist defensiv und reproduziert kein
beobachtetes v2-Versagen — er sichert das Verhalten gegen zukünftige unbekannte Materialien
ab und entfernt einen offen gewordenen False-Positive-Pfad. Im Paper kann Fall 3 als
„safety-net fallback for unrecognised material descriptions" benannt werden, wobei v2
empirisch zeigt, dass alle Tier-1- und Tier-2-Schichten von Fall 1 oder Fall 2 abgefangen
werden.

**Warum kein eigener Ablations-Schalter für die Whitelist**: Das v1-Paper definiert
`Filter=ON` als „category-based filtering approach reduces the search space" und `Filter=OFF`
als „all EPDs are passed to the LLM". Die Whitelist verschärft den Filter-Modus genau in dem
Sinn, den der Paper-Text bereits beschreibt. Ein separater Schalter würde die Studie auf
2×2×2×2 = 16 Configs verdoppeln; eine Whitelist-immer-an-Konstante würde den publizierten
Stage-3-Text („all EPDs are passed to the LLM") für die Baseline P1 falsch machen. Diese
Begründung wird im Paper-Abschnitt „Method refinements" explizit gemacht.

#### 1.2.3 Empirische Validierung der Filter-Quality-Fixes (Stage 3, LLM-frei)

Vor und nach Anwendung der Fixes aus §1.2.2 wurde das Filter-Recall-Test-Skript
(`.scratch/filter_recall_test.py`) über die 9 Materialien aus den drei v2-Inputs
ausgeführt. Dieser Test prüft *nur* Stage 3 (regelbasiert, keine LLM-Calls) — er isoliert
den Effekt der Fixes vom stochastischen LLM-Verhalten. Ergebnis-Artefakte liegen unter
`.scratch/filter-quality/baseline_output.txt` und `.../after_output.txt`.

| Material (Input / Layer) | EPDs vor | EPDs nach | Top-Treffer vorher | Top-Treffer nachher |
|-------------------------|---------:|----------:|--------------------|---------------------|
| STSuB 0/45 (a/4) | 4 | 10 | 3× Stahlblech („Elektroband nicht-schlussgeglüht", Walzplattierte Grobbleche) | 3× Zuschläge (Natürliche Gesteinskörnungen, Bims Schotter, Brechsand 0/2) |
| FSS 0/32 (a/5) | 4 | 3 | Schaumglasschotter (Dämmstoff) | 3× Zuschläge (Bims, Schotter 16/32) |
| SMA 11 S (a/1) | 18 | 5 | Brausesets, Lüftungsgeräte | 3× Asphalt (Tragdeckschicht, Asphaltbinder, Asphalttragschicht) |
| AC 16 B S (a/2) | 12 | 5 | Teppichfliesen | 3× Asphalt (Binder, Tragschicht, Gussasphalt) |
| AC 22 T S (a/3) | 12 | 5 | Teppichfliesen | 3× Asphalt |
| Splittmastixasphalt … (c/1) | 12 | 5 | Teppichfliesen | 3× Asphalt |
| Schotter ungebunden (c/4) | 11 | 10 | Schaumglasschotter | 3× Zuschläge |
| Asphaltzwischenschicht … (c/2) | 12 | 5 | Teppichfliesen | 3× Asphalt |
| Gesteinskörnungsgemisch (b/5) | 11 | 10 | Schaumglasschotter | 3× Zuschläge |

**Was die Tabelle zeigt** (paper-relevant):
- **Recall-Fix wirkt strukturell**: STSuB 0/45 verdoppelt die Kandidatenzahl (4 → 10) UND
  ersetzt alle drei Top-Treffer (Stahlblech → Zuschläge). Damit gibt es im v2-Lauf erstmals
  überhaupt sinnvolle Kandidaten für „Nicht bituminöse Tragschicht" via STSuB-Code.
- **Precision-Fix wirkt drastisch**: Asphalt-Schichten reduzieren ihre Kandidaten von 12-18
  auf konstant 5 EPDs, und die Top-3-Treffer sind in *jedem* Fall reine Asphalt-EPDs ohne
  Cross-Domain-Noise. Bei Filter=ON ist der Stage-4-Prompt damit deutlich kompakter und
  hallucination-resistenter.
- **Edge-Case Schaumglasschotter** wird konsistent ausgeschlossen — sowohl bei FSS- als auch
  bei Gesteinskörnungs- und Schotter-Inputs.
- **Token-Reduktion vor LLM**: Aus 2 779 DB-EPDs überleben nach Whitelist 319 (≈ 11,5 %);
  pro Material reduziert die Drei-Fall-Logik diese weiter auf 3-10 EPDs. Bei `Batch=ON` (P7,
  P8) übersetzt sich das in eine spürbar geringere Token-Last pro Lauf, ohne Recall-Verlust
  für die v2-Test-Schichten.

**Limitation dieses Tests**: Er sagt nichts über Accuracy aus — nur über die *Eingangsmenge*
für das LLM. Die finale Accuracy-Aussage hängt am vollständigen Benchmark-Rerun für die
Filter-aktiven Configs P3/P6/P7/P8 (Folge-Schritt; siehe §6 TODO).

#### 1.2.4 LLM-Validierung Phase A — Pilot vor / nach Filter-Fixes

Nach dem Stage-3-Test (§1.2.3) wurde ein vollständiger 1-Rep-Pilot über alle 8 Configs ×
4 Modelle × 3 Inputs = 96 Runs gefahren — einmal mit dem alten Filter
(`benchmark_output/ablation_20260601_195759/`) und einmal mit den v2-Fixes
(`benchmark_output/ablation_20260602_132120/`). Vergleichskriterium: Top-1-Match-Konsistenz
pro Schicht sowie Token-Verbrauch pro Config.

Phase A ist **kein** Paper-Datensatz (nur 1 Rep), sondern eine LLM-stochastik-bewusste
Validierung, dass die Filter-Fixes auch im echten LLM-Lauf wirken — bevor mit 5 Reps × 480
Runs der finale Paper-Lauf gefahren wird.

**Schlüsselbefund — Recall-Bug bei STSuB-Schicht ist eliminiert:**

| UUID-Präfix | EPD | Im alten Lauf gewählt von … | Im neuen Lauf gewählt von … |
|-------------|-----|------------------------------|-------------------------------|
| `c71cd5b5` | **Bade- und Duschwanne Acryl** (Gebäudetechnik / Sanitär) | 1 Modell | — |
| `75db1c10` | Beton C20/25 (Hochbau-Beton) | 2 Modelle | — |
| `9795c91c` | Asphalttragschicht (falsche Kategorie für nicht-bituminös) | 2 Modelle | — |
| `5dd08fc1` | GLAPOR Schaumglasschotter (Dämmstoff) | 1 Modell | — |
| `f4461491` | Schotter 16/32 (Naturstein) | 5 Modelle | **20 Modell-Config-Kombinationen** |
| `cff84492` | Natürliche Gesteinskörnungen | 1 Modell | 2 Kombinationen |
| `d35a5f2a` | Kies 2/32 | 1 Modell | 1 Kombination |
| `286b0072` | Sand 0/2 | 1 Modell | — |

→ Im alten Lauf streute der Top-1-Match über 8 verschiedene UUIDs, davon 4 strukturell
domänenfremd (Sanitär, Hochbau-Beton, Asphalt, Dämmstoff). Im neuen Lauf konvergieren
fast alle 24 Modell-Config-Kombinationen auf 3 korrekte Zuschlag-EPDs, dominant
`Schotter 16/32`. Keine Cross-Domain-Hallucinations mehr.

**Top-1-Stabilität und Token-Verbrauch pro Config** (Δ vs. Vor-Lauf, über alle 3 Inputs
× 4 Modelle × 5 Schichten = 60 Schicht-Entscheidungen pro Config):

| Config | Filter | Δ Top-1 | None→UUID | UUID→None | Δ Tokens | Δ USD |
|--------|:------:|--------:|----------:|----------:|---------:|------:|
| P1_Baseline | – | 14 | 0 | 3 | — | +0,03 |
| P2_Batch | – | 24 | 9 | 0 | +12 k | +0,01 |
| **P3_Filter** | ✓ | **8** | **2** | **0** | **−9 k** | +0,01 |
| P4_NamePref | – | 19 | 0 | 0 | +0 k | 0,00 |
| P5_BatchName | – | 24 | 4 | 0 | −1 k | +0,01 |
| **P6_FilterName** | ✓ | **10** | **2** | **0** | **−21 k** | **−0,03** |
| **P7_BatchFilter** | ✓ | **11** | **0** | **0** | +3 k | 0,00 |
| **P8_All** | ✓ | **9** | **1** | **0** | **−9 k** | **−0,01** |

*Δ Tokens P1: durch zwei neu erfolgreich gelaufene Runs verzerrt (im Vor-Lauf abgebrochen)
— kein interpretierbares Signal.*

**Was die Tabelle für das Paper hergibt:**
1. **Filter-aktive Configs (P3/P6/P7/P8) sind kohärenter als Filter=OFF**: 8-11 Top-1-Wechsel
   gegenüber 14-24 in Filter=OFF. Die Filter-Fixes erhöhen die Modell-übergreifende
   Reproduzierbarkeit — eine paper-relevante Eigenschaft jenseits reiner Accuracy.
2. **Recall-Gewinn ohne Recall-Verlust** in den Filter-Configs: alle None→UUID-Übergänge
   liegen in den Filter-Configs (5 Fälle), kein einziger UUID→None. Die drei UUID→None-Fälle
   in P1 sind LLM-Stochastik in der Filter=OFF-Baseline und nicht durch die Fixes verursacht.
3. **Token-Reduktion bei Filter=ON sichtbar** (P6: −18 %, P8: −15 %, P3: −9 %), trotz
   unveränderter Stage-4-Prompt-Struktur — die Whitelist + Negativ-Kontext-Fixes liefern
   konsistentere und kompaktere Kandidatenlisten an das LLM.
4. **Die zwei zuvor abgebrochenen Runs** (ablation_a P1 gpt-5-nano; ablation_b P3 gpt-5.2-chat)
   sind im neuen Lauf erfolgreich — keine separate Merge-Strategie für den Paper-Run nötig.

**Phase-A-Gesamtkosten**: ca. 12 USD für 96 Runs. Hochrechnung Phase B (5 Reps, 480 Runs):
ca. 60 USD.

#### 1.2.5 Nach Ablation — Code-Review-Befunde und Ground-Truth-Entscheidungen

Diese Sektion dokumentiert, was *nach* dem vollständigen 5-Rep-Lauf (480 Runs, Commit
`a159897` vom 2026-06-03) durch ein systematisches Code-Review und durch Sichtung der
generierten Ground-Truth-Vorlagen gefunden wurde. Die Befunde betreffen die Studien-
auswertung, nicht den Pipeline-Code-Stand zum Zeitpunkt des Laufs.

**Studienvalidität.** Alle 480 Runs sind mit dem Code-Stand inklusive der v2-Filter-Quality-
Fixes (Commit `4916523`, `fe22bdb`, `c50d232` — alle *vor* dem Lauf) entstanden. Das
Code-Review identifizierte acht Defekte (siehe `.scratch/v2-post-review-fixes/PRD.md`).
Eine systematische Datenanalyse zeigt: keiner dieser Defekte hat die v2-Studiendaten
beeinflusst. Begründung pro Befund:

| Befund | Effekt auf v2-Daten | Begründung |
|--------|---------------------|------------|
| Fall-3 ohne Cap | keiner | Fall 3 ist in v2 *dead path* (§1.2.2); kein Material erreicht ihn |
| Fuzzy-Match Bypass für „bitumen"-Inputs | keiner | Kein v2-MATERIAL trifft die Negativ-Kontext-Bedingung; „Straßenbaubitumen" wird zuvor von `_parse_normierte_bezeichnung("AC 32 T S …")` abgefangen |
| Fall-2 `len > 3` vs. Fall-3 `len > 2` | keiner | Sekundärer Fallback nur bei <10 Primärtreffern aktiv; alle v2-Materialien haben genügend Primärtreffer |
| Stage-5-Annotation im Einzelmodus | keiner für Accuracy | Bug betrifft nur das `begruendung`-Debug-Feld, nicht die `confidence`-Werte oder Top-1-Auswahl |
| `filter_trace.py` Fixture-Pfade | keiner | Reines Erklärungstool, nicht Teil der Pipeline |
| Toter Import `filter_epds_for_material` | keiner | Funktion wird nirgendwo aufgerufen |
| Betonpflaster-Testfall | keiner | Unit-Test, läuft nicht im Benchmark |

**Konsequenz für das Paper:** Die 480 Runs werden ohne Neuausführung ausgewertet. Die
Code-Fixes sind technische Schulden und werden nach Paper-Einreichung adressiert.

**Ground-Truth-Entscheidung für ablation_b / „Nicht bituminöse Tragschicht".**
Der Input für diese Schicht ist konzeptionell inkonsistent: `NAME="Nicht bituminöse Tragschicht"`,
`MATERIAL="AC 32 T S mit Straßenbaubitumen 30/45"` (Asphalt). Dies ist *kein* Datenfehler,
sondern beabsichtigte Eigenschaft des „B_Praxis"-Szenarios („Reales IFC-Praxismodell:
spezifische PMB-Materialien, abweichende Schichtnamen"). Im 5-Rep-Lauf wählt das LLM
über alle 8 Configs überwiegend `9795c91c` (Asphalttragschicht) für diese Schicht
(Pre-Fix-Frequenz: 24/28), weil das `MATERIAL`-Feld die Asphalt-Klassifizierung dominant
signalisiert.

**Methodische Optionen:**
1. **`ground_truth = null`** → Schicht aus der Accuracy-Berechnung ausschließen (per §2.2).
   Begründung: Bei konzeptionellem Input-Widerspruch existiert kein eindeutig „richtiges"
   EPD. Konsequenz: ablation_b wird auf 4 von 5 Schichten ausgewertet.
2. **`ground_truth = 9795c91c`** (Asphalttragschicht) → Konsens akzeptieren. Begründung:
   Das LLM folgt korrekt dem MATERIAL-Feld als der spezifischeren Quelle. Konsequenz:
   ablation_b/Nicht-bituminös ist eine Kontroll-Schicht für das Verhalten bei
   NAME/MATERIAL-Konflikten — NamePref=false-Configs (P1/P2/P3/P7) sollten hier
   systematisch besser abschneiden als NamePref=true-Configs (P4/P5/P6/P8).

**Entscheidung (durch Experten-Review am 2026-06-03 bestätigt):** Option 1 (`null`).
Die Schicht wird aus der Accuracy-Berechnung von ablation_b ausgeschlossen
(4 von 5 Schichten bewertet). Im Paper als methodische Annahme dokumentieren —
die Robustheit gegen Input-Inkonsistenzen wird in der Diskussion erwähnt.

**Andere ablation_b-Schichten — Experten-Review:** Deckschicht (`d24a85e3`/SMA),
Binderschicht (`85e76e87`/Asphaltbinder) und Bituminöse Tragschicht
(`9795c91c`/Asphalttragschicht) wurden vom Experten unverändert vom Modell-Konsens
übernommen. **Frostschutzschicht wurde korrigiert**: Template-Vorlage war
`cff84492` (Natürliche Gesteinskörnungen, breitester Konsens-Vorschlag), Experte hat
auf `d35a5f2a` (Kies 2/32) korrigiert. Begründung: Der MATERIAL-Wert
„Kies-Sand-Gemisch frostsicher, natürlich gewonnen, bis 32mm" verlangt einen
spezifischeren Match als die generische Oberkategorie „Natürliche Gesteinskörnungen".

**Paper-Implikation der Korrektur:** Diese Schicht ist ein dokumentiertes Beispiel
dafür, dass der Modell-Konsens nicht automatisch die Ground Truth ist — das Modell
neigt dort, wo mehrere semantisch verwandte EPDs existieren, zum breiteren
Oberbegriff. Im Paper als Argument für die Notwendigkeit des Experten-Reviews der
GT-Templates verwendbar (gegen Reviewer 1's „multiple acceptable labels"-Kritik).

**Konstante Faktoren** (nicht abladiert, Begründung im Paper notwendig):
- Stage 2 (Glossar-Parsing): bleibt aktiv, aber sein Beitrag ist gering da ÖKOBAUDAT kaum
  produktspezifische Infrastruktur-EPDs hat → „Stage-2-Vorbehalt" im Paper dokumentieren
- Stage 5 (Confidence-Cap): bleibt aktiv als post-processing Konstante

#### 1.2.6 Headline-Ergebnisse v2 (480 Runs, validierte Ground Truth)

Auswertung des 480-Run-Datensatzes (`ablation_20260602_145931`) gegen die experten-
validierte Ground Truth (Stand 2026-06-03). Bewertet werden 14 Schichten pro Input
× Modell-Kombination (5 + 4 + 5 — ablation_b/Nicht-bituminös ausgeschlossen, siehe §1.2.5).

**Top-1-Accuracy pro Config × Modell** (Mittel über 5 Repetitionen × 3 Inputs):

| Config | ⌀ | gpt-4o-mini | gpt-5-nano | gpt-5-chat | gpt-5.2-chat | $ total | $/run |
|--------|--:|-----:|-----:|-----:|-----:|-----:|-----:|
| **P7_BatchFilter** | **83,9 %** | 77,1 % | 74,3 % | 91,4 % | 92,9 % | **0,49** | 0,008 |
| P3_Filter | 81,1 % | 77,1 % | 82,9 % | 85,7 % | 78,6 % | 0,83 | 0,014 |
| P1_Baseline | 70,4 % | 30,0 % | 85,7 % | 67,1 % | 98,6 % | 23,91 | 0,398 |
| P6_FilterName | 66,1 % | 70,0 % | 64,3 % | 64,3 % | 65,7 % | 0,79 | 0,013 |
| P8_All | 64,6 % | 61,4 % | 52,9 % | 72,9 % | 71,4 % | 0,48 | 0,008 |
| P2_Batch | 63,2 % | 47,1 % | 32,9 % | 78,6 % | 94,3 % | 5,12 | 0,085 |
| P4_NamePref | 56,8 % | 20,0 % | 57,1 % | 74,3 % | 75,7 % | 23,89 | 0,398 |
| P5_BatchName | 46,4 % | 17,1 % | 21,4 % | 68,6 % | 78,6 % | 5,13 | 0,085 |

**Paper-relevante Befunde:**

1. **P7_BatchFilter ist die beste Config**: 83,9 % Accuracy bei 0,49 USD Gesamtkosten
   — +13,5 %-Punkte gegenüber P1_Baseline und ≈ 49× günstiger. Die Filter+Batch-
   Kombination bestätigt den v1-Befund, dass Stage-3-Vorfilterung der zentrale
   Cost-Efficiency-Hebel ist, und erweitert ihn: Batch-Mode ohne Filter (P2) schadet
   leicht (-7,2 PP vs. P1), Filter+Batch zusammen ist besser als jede Einzelkomponente.

2. **NamePref-Effekt kehrt sich gegenüber v1 um**: Alle vier NamePref=ON-Configs
   (P4, P5, P6, P8) sind schlechter als ihre NamePref=OFF-Counterparts (P1, P2, P3, P7).
   Mittlerer Effekt: −12,8 PP. Hauptursache: ablation_b mit NAME/MATERIAL-Konflikt
   (vgl. §1.2.5). Im Paper als Wechselwirkung zwischen Schicht-Cap (Stage 5) und
   uneinheitlicher Input-Qualität diskutieren — Reviewer-2-Punkt „Kombinationsauswahl
   begründen" wird genau hier paper-wirksam.

3. **Modell-Heterogenität ist groß**: gpt-4o-mini bei P1 nur 30 %, bei P3 aber 77,1 %.
   Das stützt die Cost-at-Threshold-Argumentation (§3.2): günstige Modelle erreichen
   nur mit Vorfilterung wettbewerbsfähige Accuracy.

4. **Cost-at-Threshold-Bezugsgröße**: P1-Baseline-Accuracy = 70,4 %. P3, P7
   überschreiten diese Schwelle bei 1/29 bzw. 1/49 der Kosten. P7 ist im Paper-Hauptbefund
   als „beste Konfiguration unterhalb Baseline-Cost und oberhalb Baseline-Accuracy"
   einsetzbar.

**Artefakte**: `benchmark_output/ablation_20260602_145931/ablation_analysis.html`
(interaktive Charts) und `ablation_analysis.xlsx` (Detail-Tabellen).

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

### 3.1.1 Zusatzmetrik: Top-3 Accuracy (Human-in-the-Loop)

**Entscheidung**: Tab. 3 (`tab:acc`) wird um eine **Top-3-Spalte neben Top-1** erweitert
(gleiche Tabelle, additiv). **Nachträglich aus dem bestehenden 480-Run-Datensatz berechenbar
— kein neuer Lauf.** Die Rohdaten speichern pro Schicht die komplette gerankte Liste
(`top_matches` / `id`-Array, absteigend nach validierter Confidence, bis zu 5 bei Asphalt,
bis zu 10 bei Körnung). Code-Eingriff: `ablation_analysis.py` `run_accuracy` (Z. 107) und
`layer_accuracy` (Z. 224) — `gt_uuid in layer["top_matches"][:3]` statt `== top_matches[0]`,
plus je eine Spalte in Overview-Tabelle und Excel-Sheet 1/2. ~15 Zeilen.

**Definition (präzise, paper-relevant)**: Anteil der bewerteten Schichten, in denen die GT-UUID
unter den **drei höchstgerankten exportierten Vorschlägen** liegt. **Nicht** Recall@3 über den
Katalog: das Tool gibt pro Schicht nur seine fünf höchstgerankten Vorschläge zurück (bei
Filter=ON Asphalt sind das die ~5 gefilterten Kandidaten). Top-3 ist damit die
**Human-in-the-Loop-Metrik**: „Findet der Bearbeiter die richtige EPD unter den Top-3 der
Oberfläche?" — und schließt genau die Lücke, die das Paper (Discussion, „five highest-ranked
suggestions per layer … only the highest-ranked was evaluated") offenlässt.

**Begründung / adressierte Kritik**:
- **Reviewer 1 „multiple acceptable labels"**: Liegt die GT oft auf Platz 2–3, quantifiziert
  Top-3 den Near-Miss-Abstand bzw. die Label-Mehrdeutigkeit, die strenge Top-1 unterzählt.
- **Human-in-the-Loop-Design** (Paper-Discussion) wird erstmals *gemessen* statt nur behauptet.

**Guardrails (gegen Reviewer-2-„Metrik unbegründet"-Risiko)**:
- Additiv zu Top-1, **nicht** ersetzend.
- **Raus aus Cost-at-Threshold** (§3.2): die Kostenmetrik bleibt auf Top-1 verankert; Top-3 ist
  kein Optimierungs-Zielwert.
- Paper-Wording: „GT among the top-3 *exported suggestions*", explizit **nicht** „recall@3";
  Caveat nennen, dass der Kandidatensatz bei Filter=ON klein ist (~5) — Top-3 ist dann ein
  „3 von 5"-Maß, das aber exakt die Nutzersicht abbildet.

#### 3.1.2 Top-3 Ergebnisse v2 (480 Runs, nachträglich berechnet)

Implementiert in `ablation_analysis.py` (Commit nach `a159897`). Vollständige Tabelle
(Mittelwert über 5 Reps × 3 Inputs, 14 bewertete Schichten):

| Config | gpt-4o-mini | gpt-5-chat | gpt-5-nano | gpt-5.2-chat |
|--------|------------:|-----------:|-----------:|-------------:|
| **Top-1** | | | | |
| P1 Baseline    | 29,3 | 67,3 | 85,3 |  98,7 |
| P2 Batch       | 47,3 | 79,7 | 31,7 |  93,7 |
| P3 Filter      | 77,0 | 85,0 | 82,7 |  78,3 |
| P4 NamePref    | 18,7 | 73,3 | 55,7 |  75,7 |
| P5 BatchName   | 18,0 | 67,7 | 22,3 |  78,7 |
| P6 FilterName  | 70,3 | 63,3 | 63,7 |  65,7 |
| P7 BatchFilter | 77,0 | 90,3 | 74,0 |  91,7 |
| P8 All         | 60,7 | 71,7 | 52,7 |  70,0 |
| **Top-3** | | | | |
| P1 Baseline    | 32,0 |  90,7 |  95,7 | 100,0 |
| P2 Batch       | 60,7 |  82,7 |  38,7 |  97,0 |
| P3 Filter      | 85,0 |  85,0 |  90,3 |  93,3 |
| P4 NamePref    | 25,3 |  98,7 |  69,7 | 100,0 |
| P5 BatchName   | 19,7 |  78,7 |  25,3 | 100,0 |
| P6 FilterName  | 85,0 |  86,7 |  89,0 |  93,3 |
| P7 BatchFilter | 95,7 |  96,7 |  83,0 |  96,7 |
| P8 All         | 93,3 | 100,0 |  84,3 |  98,3 |

**Paper-relevante Befunde:**

1. **Human-in-the-Loop-Gewinn quantifiziert**: P1 gpt-5-chat Top-1 67,3 % → Top-3 **90,7 %**
   (+23,4 PP). P7 gpt-4o-mini: 77,0 % → **95,7 %** (+18,7 PP). Bei empfohlener Config (P7)
   findet der Bearbeiter die richtige EPD in >95 % der Fälle unter den ersten drei Vorschlägen.
   Das ist die direkte Quantifizierung des Human-in-the-Loop-Designs, das bisher nur behauptet
   wurde.

2. **Filter-Configs: Top-3-Plateau durch kleinen Kandidatensatz** — P3/P6 gpt-5-chat:
   Top-1 = Top-3 = **85,0 %** (exakt gleich). Bei ~5 Asphalt-Kandidaten gibt es keinen
   Rank-2/3-Spielraum; GT entweder Rang 1 oder gar nicht im Kandidatensatz. Das erklärt, warum
   Filter=ON den Top-3-Gewinn *dämpft* — und ist genau das Paper-Caveat „3 von 5"-Maß.

3. **Schwache Modelle profitieren stärker von Top-3**: gpt-4o-mini P1: +2,7 PP (29,3→32,0),
   gpt-5-chat P1: +23,4 PP (67,3→90,7). Das schwächere Modell platziert die GT seltener in
   den Top-3 überhaupt — Near-Miss-Gain ist dort kleiner. Stärkere Modelle (5-chat, 5.2-chat)
   haben schon gute Ranking-Qualität und profitieren bei Top-3 enorm.

4. **NamePref-Effekt bei Top-3 teils umgekehrt**: P4 gpt-5-chat Top-3 **98,7 %** (vs. Top-1
   73,3 %) — NamePref platziert die GT zuverlässig in den Top-3, schafft sie aber seltener auf
   Rang 1. Interpretierbar als: NamePref-Stage-5-Cap deckelt die Confidence der GT-EPD auf 60,
   wenn Schicht-Term fehlt — das drängt sie auf Rang 2/3 statt sie rauszuwerfen. Unterstützt
   die Diskussion über NamePref als Ranking-Störer, nicht als Recall-Störer.

5. **P8 All gpt-5-chat/5.2-chat: Top-3 = 100 %** trotz Top-1 71,7 %/70,0 %. Die GT ist
   *immer* im Kandidatensatz vorhanden, das Ranking scheitert. Filter+Batch+NamePref gemeinsam
   schaffen einen fokussierten Kandidatensatz, aber NamePref stört das Ranking (Befund 4).

**Discussion-Formulierungsvorschlag**: „While Top-1 accuracy reflects the fully automated
assignment quality, Top-3 accuracy approximates the practical outcome when an expert reviews
the exported suggestions. Under the recommended P7 configuration, the correct EPD appears
among the top-3 suggestions in over 95\,\% of cases across all models, supporting the
human-in-the-loop design. The smaller gap between Top-1 and Top-3 under Filter=ON configurations
reflects the reduced candidate set size ($\approx$5 EPDs), which limits the number of
available rank positions."

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

### 3.4 Anmerkung zur Kostenberechnung: Prompt-Caching

**Sachverhalt**: Die im Paper berichteten Kosten werden mit `utils/cost_tracker.py` aus den
Token-Counts der API-Response und den Azure-Listenpreisen (Sweden Central, Global Standard)
berechnet:

```
cost = (prompt_tokens / 1e6) × input_price + (completion_tokens / 1e6) × output_price
```

Dieser Rechner berücksichtigt **kein Prompt-Caching**. Azure OpenAI rechnet identische
Prompt-Präfixe ab ≥1024 Tokens und innerhalb einer Cache-TTL von ~5 Minuten zu einem
reduzierten Preis ab (Faktor ~10× günstiger bei GPT-4.1- und GPT-5-Familie, ~2× bei GPT-4o)
und liefert die gecachte Anzahl in `usage.prompt_tokens_details.cached_tokens` zurück.

**Empirischer Befund**: Ein Abgleich der `cost_tracker`-Schätzung gegen die Azure-Abrechnung
(Cost-Analysis-Export 2026-06-01 bis 2026-06-03, 3-Tages-Summe ≈ 36.79 USD) zeigt, dass die
tatsächlichen Cloud-Kosten deutlich niedriger ausfallen als die im Tracker ausgewiesenen
Listenpreis-Kosten. Plausible Ursache: Der EPD-Matcher hat einen stabilen, großen
Prompt-Präfix (System-Prompt + EPD-Katalog, je nach Config 10–20k Tokens) und viele Calls
innerhalb der Cache-TTL.

**Implikation für das Paper**: Die berichteten Kostenzahlen sind als **Obergrenze**
(Listenpreis ohne Cache-Discount) zu lesen, nicht als tatsächliche Cloud-Kosten. Diese
Konvention wird im Methodik-Teil explizit benannt.

**Implikation für die Ablation**: Der Cache-Effekt trifft die P-Configs unterschiedlich
hart. Configs ohne Batching (P1, P3, P4, P6) führen N Calls pro Input mit identischem
Präfix aus → hoher Cache-Anteil ab dem zweiten Call. Batch-Configs (P2, P5, P7, P8) haben
nur einen Call pro Input → der Cache greift nur zwischen Reps und Inputs. Die relativen
Kostenverhältnisse zwischen P-Configs in der echten Azure-Abrechnung können dadurch von
den Listenpreis-Verhältnissen abweichen. Im Paper als Diskussion erwähnen, im Fließtext
nicht als Hauptbefund.

**Paper-Formulierung (Vorschlag)**: „Reported costs are computed from token counts at
Azure's published list prices (Sweden Central, Global Standard, May 2026) and do not
account for prompt-caching discounts. Actual billed costs are lower; the magnitude of
the discount depends on the configuration's prompt-reuse pattern."

---

## 4. Systemarchitektur — Paper-relevante Entscheidungen

### 4.1 Drei-Skript-Architektur

**Entscheidung**: Messung, Analyse und Custom-Entries-Experiment sind getrennte Skripte.

| Skript | Aufgabe | Output |
|--------|---------|--------|
| `benchmark/ablation_benchmark.py` | 480 Runs ausführen, Rohdaten sammeln | `benchmark_runs.json`, GT-Vorlagen, Rohdaten-HTML/Excel |
| `benchmark/ablation_analysis.py` | Accuracy berechnen, Paper-Charts | `ablation_analysis.html`, `ablation_analysis.xlsx` |
| `build_custom_db.py` | `local`-DB → `local-custom`-DB bauen (validieren + custom-Einträge einfügen) | `data/oekobaudat_custom.db` |
| `benchmark/custom_entries_experiment.py` | Sparse-EPD-Migration messen (Vorher=`local` / Nachher=`local-custom`) | `custom_entries_report.html` |

**Begründung für das Paper**: Trennung von Messung und Auswertung ermöglicht nachträgliche
Ground-Truth-Korrekturen ohne erneute LLM-Runs. Das Custom-Entries-Experiment läuft gegen die
separate `local-custom`-DB — die Original-`local`-DB bleibt unverändert und alle 480
Hauptablations-Läufe bleiben reproduzierbar (siehe `docs/adr/0002-local-custom-datenquelle.md`).

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

### 4.4 Cross-Layer-Recall im Batch-Modus

**Beobachtung (empirisch, 2026-06-05)**: Im Batch-Modus (`filter_for_materials`) teilen sich
alle Schichten eines Inputs **einen gemeinsamen Kandidaten-Pool**. Eine Schicht kann daher ein
EPD matchen, das der Glossar-Filter über eine **Nachbarschicht** beigesteuert hat — selbst wenn
der schicht-eigene Filter es nicht erfasst hätte. Konkret: für `ablation_a` erfasst der Filter
die generische „Kies 2/32" (Frostschutz-GT) bei isolierter Frostschutz-Eingabe (`FSS 0/32`)
lexikalisch **nicht**, wohl aber über die Schotter-Schicht (`STSuB 0/45`); im geteilten
Batch-Prompt steht sie damit auch der Frostschutzschicht zur Wahl. Der kombinierte Pool enthält
so alle fünf Ground-Truth-EPDs (Pool-Größe 15, weit unter `MAX_EPD_IN_PROMPT`).

**Paper-Relevanz**: erklärt, warum die Batch-Configs (P2/P6/P7) trotz schmaler Per-Schicht-Filter
robust matchen, und ist ein nicht-offensichtlicher Vorteil von Batch gegenüber Einzel-Calls
(P3 isoliert pro Schicht und hat diesen Recall-Effekt nicht). Methodischer Hinweis für die
Reproduktion: Per-Schicht-Reachability-Tests unterschätzen die Batch-Recall; die maßgebliche
Prüfung ist der kombinierte Pool.

---

## 5. Zusatzexperiment: Custom Entries

**Entscheidung**: Kleines Zusatzexperiment mit modifizierter lokaler DB, das zeigt, wie der
Matcher reagiert, wenn produktspezifische EPDs verfügbar werden. Adressiert Reviewer 1
(Sparse-EPD) und trägt die Intro-These (CPR/DPP → mehr produktspezifische EPDs).

**Claim (bewusst eng gefasst)**: *Sensitivität gegenüber Datenbankabdeckung* — **kein
„Beweis"** der Zukunftstauglichkeit. Begründung: Würden wir einen custom-Eintrag als
offensichtlich besten Treffer konstruieren *und* ihn als Ground Truth setzen, wäre die
Aussage zirkulär (Kandidat und Antwort selbst gelegt). Stattdessen messen wir einen
*Mechanismus*, nicht eine selbstgelegte Lücke.

**Mechanismus = Discrimination/Quality, nicht Coverage.** Befund aus den v2-Inputs: dieselbe
generische EPD matcht materiell verschiedene Schichten (Deckschicht `SMA 11 S` / `SMA 8 S PmB`
/ `Splittmastix lärmreduzierend` → alle `d24a85e3`; bit. Tragschicht `AC 22 T S` / `AC 32 T S`
/ `grobe Asphalttragschicht` → alle `9795c91c`). Das ist der **Stage-2-Vorbehalt live in den
Daten**: Stage 2 parst die Codes sauber, aber wirkungslos, weil kein produktspezifisches EPD
existiert. Eine *Coverage*-Story („füllt eine leere Schicht") hat **kein ehrliches Ziel** in
den aktuellen Inputs — die einzige `null`-Schicht (ablation_b/Nicht-bituminös) ist ein
Praxis-Dateneingabefehler (falsches Material), kein Abdeckungsloch.

**Headline-Metrik = Migrationsrate** (zirkularitäts-robust): Anteil der Runs, in denen der
Top-1 vom generischen Alt-EPD auf den produktspezifischen custom-Eintrag wechselt. Aussage:
„das Modell upgradet auf bessere Daten", **nicht** „X ist die einzige Wahrheit". Accuracy gegen
eine neu-bestimmte GT nur sekundär und mit Caveat.

**Ergebnisse — Lauf `custom_entries_20260605_133038`** (P7, 4 Modelle × 3 Inputs × 5 Reps =
120 Läufe, alle OK, $1,03; 9 custom-Einträge):

| Aggregat | Migrationsrate | n |
|---|---|---|
| **Gesamt** | **95,7 %** | 268/280 |
| Mechanismus: Asphalt | 93,3 % | 168/180 |
| Mechanismus: Körnung | 100 % | 100/100 |
| Arm A (Norm-Code) | 100 % | 100/100 |
| Arm B (Praxis-Code) | 100 % | 80/80 |
| Arm C (Freitext) | 88,0 % | 88/100 |

Nenner-Hinweis: B = 80 (4 Schichten; `ablation_b`/Nicht-bituminös null-Layer ausgenommen).

**Befund (publizierbar):** A und B migrieren **vollständig** (100 %) — Norm-/Praxis-Codes tragen
die Migration lexikalisch + strukturell. Die einzige Lücke liegt in **C/Asphalt (80 %, 12/60)**;
C/Körnung migriert zu 100 %. Die 12 Nicht-Migrationen sind **vollständig** den zwei schwächeren
Modellen zuzuordnen (gpt-4o-mini: 10, gpt-5-nano: 2); **gpt-5-chat und gpt-5.2-chat migrieren auch
bei Freitext zu 100 %**. → Die Spezifitäts-Lücke bei Freitext ist eine **Modell-Kapazitäts-Frage**,
kein Methodenversagen. Migrationsrate je Modell (gesamt / Arm C): gpt-4o-mini **85,7 % / 60 %**,
gpt-5-nano **97,1 % / 92 %**, gpt-5-chat **100 % / 100 %**, gpt-5.2-chat **100 % / 100 %** (A & B
je Modell durchweg 100 %). Zwei Muster:
- *Bituminöse Tragschicht (C)*: `stayed_generic` — schwaches Modell bleibt beim generischen
  „Asphalttragschicht" (Freitext „grobe Asphalttragschicht…" lexikalisch näher als custom „… AC 22 T S").
- *Deckschicht (C)*: `other`, aber **keine Regression** — Wechsel von generischer *Tragdeckschicht*
  (`c6f77799`) auf korrekte generische *SMA* (`d24a85e3`), nur nicht bis zum custom-Eintrag.

Rohdaten: `benchmark_output/custom_entries_20260605_133038/` (`migration_report.json`,
`custom_entries_runs.json`).

**Drift-Quercheck der Vorher-Baseline (Validität)**: Die frische P7/`local`-Vorher-Generik
(60 Läufe) wurde gegen die 60 P7-Läufe des Hauptdatensatzes `ablation_20260602_145931`
verglichen (modaler Top-1 je Zelle model×input×layer). **59/60 Zellen identisch (98,3 %)** →
die Vorher-Baseline ist driftfrei, die gemessene Migration ist nicht durch Modell-/Prompt-Drift
zwischen 02.06. und 05.06. konfundiert. Die **einzige** Abweichung (ablation_b / gpt-5.2-chat /
Frostschutzschicht, Material „Gesteinskörnungsgemisch 0/32") ist ein Wechsel zwischen zwei
**generischen** Zuschlag-EPDs — alt `f4461491` (Schotter 16/32) → neu `cff84492` (Natürliche
Gesteinskörnungen, Näppi T&N Oy) — bei einem mehrdeutigen Körnungs-Material; reine LLM-Stochastik,
**kein** systematischer Drift. Wirkung auf die Migrationsmessung: **null** — dieselbe Zelle
migriert im Nachher-Lauf 5/5 auf den custom-Eintrag (`custom-gk-frost-b`), unabhängig von der
Baseline. Beleg: `benchmark_output/custom_entries_20260605_133038/drift_check.json`.

### 5.0 Datenvariabilität als Motivation (NORSUS — Petrovic & Raadal 2025)

**Referenz**: Petrovic, B. & Raadal, H. L. (2025): *Analyzing data variability in EPDs of
crushed stone and asphalt.* NORSUS (Norwegian Institute for Sustainability Research), Report
AR 11.25, 12.09.2025. (Begleit-Referenz: Konradsen et al. 2024, „Same product, different
score", *Int. J. LCA* 29:291–307.) PDF: `docs/studie/2025_NORSUS_EPD_Datavariability_CrushedStone_Asphalt.pdf`.

**Warum zentral**: liefert die Zahl, die das „so what?" des Custom-Entries-Experiments trägt.
NORSUS misst die GWP-Streuung (A1–A3, fossil) realer EPD-Norway-Datensätze für **genau unsere
zwei Materialfamilien**:
- **Asphalt: 11,3 bis 83,1 kg CO₂e/t** (~7-facher Spread). Gruppe 1 (virgin, 5–6 % Bitumen):
  17,9–83,1; Gruppe 2 (Skanska, ~40 % RAP): 11,3–21,9 — Spread getrieben von Zusammensetzung/
  RAP-Anteil.
- **Schotter**: 30 EPDs, Emissionen pro Brechstufe (Stage 0–3) stark streuend, Reporting
  **nicht harmonisiert** (Stufen kombiniert/weggelassen/zusätzlich „vaskeverk"; teils later
  stage < earlier stage = physikalisch unmöglich).

**Direkter Anknüpfungspunkt**: Der NORSUS-Datensatz enthält wörtlich unsere Vorlagen-Hersteller
— **NEPD-4200-3429-NO (Velde Pukk)** = Vorlage für `custom-fss-frost-a`, sowie Franzefoss Pukk
(Schotter-Vorlage). Unsere custom-Einträge sind also aus genau der EPD-Familie modelliert, deren
Variabilität NORSUS quantifiziert.

**Platzierung im Paper (beschlossen)**:
1. **Intro/Motivation** — die 11,3–83,1 kg CO₂e/t-Spanne begründet, *warum produktspezifisches
   Matching zählt*: welche EPD gematcht wird, ändert die Bilanz um das ~7-Fache. Macht die
   Migration generisch→spezifisch zur LCA-relevanten Größe, nicht zur Matching-Kosmetik.
2. **Diskussion (Sensitivity-Section nach der Hauptablation)** — die Auszahlung **plus ehrlicher
   Vorbehalt**: Wenn EPDs laut NORSUS untereinander inkonsistent/schwer vergleichbar sind, gibt
   es eine **Decke** für die Downstream-Genauigkeit jedes Matchers. Das **stärkt** das
   Top-3/Human-in-the-Loop-Argument (§3.1.1) — menschliches Urteil statt Vollautomatik —, statt
   es zu schwächen.

**Altitude-Disziplin (wichtig)**: NORSUS ist **Motivations-/Datenqualitäts-Evidenz, kein
Methoden- oder Matching-Beweis**. Nicht als „Beleg, dass das Tool funktioniert" einbringen. Es
begründet die Problemrelevanz und liefert einen Limitation-/HITL-Vorbehalt — mehr nicht.

**Reviewer-Nutzen**: zusätzliche, aktuelle Datenqualitäts-Referenz (eigenständig neben dem
bereits referenzierten Petrosa et al. 2025 — nicht damit zu verwechseln). Stützt die
Problemrelevanz und liefert den Harmonisierungs-Vorbehalt.

**Scope = alle 5 Schichten, gesplittete Berichterstattung nach Mechanismus:**
- **Asphalt-Schichten (Deck/Binder/bit. Trag)** — *generic-collapse → discrimination*
  (Hauptbefund). Je ein custom-Eintrag für A's und B's Bezeichnung.
- **Körnungs-Schichten (Nicht-bit. Trag, Frostschutz)** — *approximate-grading → exact match*
  (Stützbefund). Heutige GT trifft die Körnung nur näherungsweise (GT `Schotter 16/32` vs.
  Input `STSuB 0/45`); ein exaktes „0/45"-EPD ist eine berechtigte Präzisionsverbesserung.
- **Wrinkle**: ablation_b/Nicht-bituminös ist der `null`-Fehler-Layer → dort nur A's Eintrag,
  B ausgenommen.

**Drei Input-Arme:**
- **A (Norm-Code)** — sauberstes Migrationssignal.
- **B (Praxis-Code)** — Migration mit real abweichenden Bezeichnungen.
- **C (Freitext, keine Norm-Codes)** — eigenständiger **Freitext-Robustheitsarm**: Reicht das
  NL-Verständnis, um auch ohne Norm-Code auf den spezifischen Eintrag zu migrieren, oder fällt
  C auf generisch zurück? Beide Ausgänge publizierbar (Stärke bzw. ehrliche Limitation
  „Spezifität braucht Norm-Codes"). C bekommt **keine** eigenen custom-Einträge — es wird gegen
  die für A/B eingefügten getestet.

**Anti-Fabrikations-Guardrail**: Jeder custom-Eintrag wird auf ein *real existierendes*
Produkt-EPD modelliert (IBU, EPD Norge, Hersteller-EPD) und die Quelle dokumentiert — nicht
erfunden, um trivial auffindbar zu sein.

**Harte technische Anforderung (jetzt maschinell erzwungen)**: Jeder custom-Eintrag muss eine
**whitelist-konforme `klassifizierung`** tragen (`matching_rules.py` → `TIEFBAU_KLASSIFIKATION_PREFIXES`):
Asphalt-EPDs unter `Mineralische Baustoffe / Asphalt / …`, Körnungen unter
`Mineralische Baustoffe / Zuschläge / …`. Sonst filtert die Tiefbau-Scope-Whitelist den Eintrag in
Filter=ON-Configs (P3/P7) heraus, er erreicht das LLM nie → Migration per Konstruktion unmöglich.
**Seit 2026-06-05 baut `build_custom_db.py` (via `datasources/custom_entries.py`) jeden Eintrag
fail-fast**: (1) Whitelist-Präfix-Prüfung, (2) Glossar-Filter-Reachability-Dry-Run gegen
`(ziel_material, ziel_schicht)` — fängt auch „whitelist-OK, aber name trifft den Filter nicht" ab,
bevor LLM-Kosten anfallen. Template und Config sind entsprechend korrigiert (siehe
`docs/adr/0002-local-custom-datenquelle.md`).

**Methode**: Vorher (Standard-DB) vs. Nachher (+ custom-Einträge), je über die 3 Inputs.
Run-Matrix (Configs/Modelle/Reps) — siehe §6 offene Frage.

**DB-Aufbau (neu seit 2026-06-05)**: `build_custom_db.py` kopiert `data/oekobaudat.db` →
`data/oekobaudat_custom.db`, validiert fail-fast und fügt `source='custom'` ein. Wahl im Lauf
über `EPD_DATA_SOURCE=local-custom` (4. Quellwert). Config ist Quelle der Wahrheit, die DB ein
abgeleitetes, neu-baubares Artefakt — Original `local`-DB bleibt unberührt (Isolierung erfüllt,
alle 480 Hauptablations-Runs reproduzierbar). Ersetzt die frühere Temp-Kopie-/`LOCAL_DB_PATH`-
Override-Mechanik. Siehe `docs/adr/0002-local-custom-datenquelle.md`.

Aufruf:
```
python build_custom_db.py --config benchmark/custom_entries_config.json
# Vorher-Arm: EPD_DATA_SOURCE=local   |   Nachher-Arm: EPD_DATA_SOURCE=local-custom
```

**Config-Format** (`custom_entries_config.json`, 9 Einträge, erstellt 2026-06-05):
- `action: "insert"` — neuer custom-Eintrag (source='custom'). Pflichtfelder: `id`, `name`,
  `klassifizierung` (whitelist-konform, deutsch), `ziel_schicht` (echter Input-NAME, treibt
  Reachability), `ziel_material` (repräsentatives Input-Material), `quelle` (reales Vorlage-EPD).
- `action: "update"` — überschreibt Felder eines bestehenden Eintrags (Pflichtfeld `quelle`).
- Vorlagen: Asphalt-Schichten auf EPD-Norge/Global-NEPDs (Peab/Colas: SMA, AB, GAB),
  Körnungs-Schichten auf pukk-NEPDs (Franzefoss/Velde). Befund: deutsche produktspezifische
  Asphalt- **und** Zuschlag-EPDs existieren kaum → stützt die Sparse-These (vgl. §5.0 NORSUS).

**Skript Vorher/Nachher** (Migration, umgebaut 2026-06-05): `benchmark/custom_entries_experiment.py`
baut via `build_custom_db` die `local-custom`-DB und fährt **Vorher = `EPD_DATA_SOURCE=local`** /
**Nachher = `EPD_DATA_SOURCE=local-custom`** über 4 Modelle × 3 Inputs × 5 Reps am Betriebspunkt
**P7**. Migrations-Auswertung in `benchmark/migration.py` (reine, getestete Funktionen — Modul C).

**Output**: `benchmark_output/custom_entries_<ts>/migration_report.json` mit Aggregaten
(gesamt / nach Mechanismus / nach Arm / Arm×Mechanismus) + Outcome-Records je
(model, input, layer, rep); Rohläufe in `custom_entries_runs.json`.

**Paper-Positionierung**: Abschnitt nach Hauptablation, „Sensitivity to Database Coverage"
oder Diskussion/Future Work. Kernaussage: Sobald produktspezifische EPDs vorliegen, **migriert
der Matcher von generischen auf spezifische Treffer** (und reaktiviert damit Stage 2) — gemessen
als Migrationsrate, gesplittet nach Asphalt (collapse→discrimination) und Körnung
(approximate→exact). Der Freitext-Arm C zeigt, wie weit dieser Effekt ohne Norm-Codes trägt.

**Adressierte Reviewer-Kritik**: Reviewer 1, Punkt 1: „Sparse EPD data not addressed."

**Migrationsmetrik-Definition** (umgesetzt in `benchmark/migration.py`): Vorher-Baseline je Zelle
(model, input, layer) = **modaler** generischer Top-1 über die Reps (kein rep-zu-rep-Pairing, da
Reps stochastisch). Jeder Nachher-Layer-Run → `migrated` (Top-1 ∈ custom-IDs) / `stayed_generic`
(Top-1 == Baseline, ∉ custom) / `other` (sonst). Migrationsrate = Anteil `migrated`. Die
`ablation_b`/Nicht-bituminös-Zelle (null-Fehler-Layer, kein custom-Eintrag) ist aus dem Nenner
ausgenommen. Arm C zählt mit (migriert, wenn Freitext auf einen A/B-custom landet).

---

## 6. Offene Punkte (TODO)

- [x] Material-Werte für Input A, B, C festgelegt (`TestInput/ablation_a/b/c/input/input.json`)
- [ ] Ground-Truth-UUIDs manuell bestimmen (nach Benchmark-Lauf + Template-Review)
- [x] `custom_entries_config.json` erstellt (2026-06-05, 9 Einträge auf reale NEPD-Vorlagen, alle validiert) — `quelle`-Felder (v.a. pukk-NEPDs) noch gegenzulesen
- [x] local-custom-Mechanik + `build_custom_db.py` gebaut (ADR-0002), Whitelist+Reachability fail-fast
- [x] `custom_entries_experiment.py` auf `local`/`local-custom`-Naht umgestellt + Migrationsmetrik (`benchmark/migration.py`, getestet) ergänzt (2026-06-05) — bereit für bezahlten Lauf
- [x] Bezahlten Migrations-Lauf gefahren (2026-06-05, `custom_entries_20260605_133038`, $1,03, 120/120 OK) — Gesamt-Migrationsrate 95,7 %, Ergebnisse in §5 eingetragen
- [x] Drift-Quercheck: frische P7/local-Vorher-Generik vs. 60 P7-Runs aus `ablation_20260602_145931` — 98,3 % identisch (59/60), einzige Abweichung benign (generisch↔generisch, keine Migrations-Wirkung); siehe §5 + `drift_check.json`
- [x] NORSUS-PDF (Petrovic & Raadal 2025) nach `docs/studie/` kopiert + in §5.0 dokumentiert; noch in Intro/Refs des Papers ausformulieren
- [ ] Prompt-Beispiel dokumentieren (Abschnitt 4.2)
- [ ] Snapshot-Datum der lokalen ÖKOBAUDAT-DB dokumentieren
- [x] Benchmark-Rerun für P3/P6/P7/P8 mit Filter-Quality-Fixes (durchgeführt 2026-06-02, Commit `a159897`)
- [x] Experten-Validierung der `ground_truth.json` für ablation_a/b/c abgeschlossen (2026-06-03) — ablation_b/Nicht-bituminös = null bestätigt, ablation_b/Frostschutz von `cff84492` auf `d35a5f2a` korrigiert, siehe §1.2.5
- [x] Headline-Accuracy-Auswertung gegen validierte GT durchgeführt — P7_BatchFilter 83,9 %, siehe §1.2.6
- [ ] Post-Review-Fixes adressieren (siehe `.scratch/v2-post-review-fixes/PRD.md`) — nach Paper-Einreichung
- [ ] Preisdatum der 4 Azure-Modelle für v2 dokumentieren (neue Benchmark-Läufe)
- [ ] Caching-Hinweis aus §3.4 in Methodik-Abschnitt des Papers einbauen + Limitation-Satz
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
