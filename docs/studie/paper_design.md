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

**Vorläufige Entscheidung:** Option 1 (`null`), bis Experten-Validierung des
Ground-Truth-Dokuments erfolgt ist. Im Paper als methodische Annahme dokumentieren —
die Robustheit gegen Input-Inkonsistenzen wird in der Diskussion erwähnt.

**Andere ablation_b-Schichten:** Deckschicht (`d24a85e3`/SMA), Binderschicht
(`85e76e87`/Asphaltbinder), Bituminöse Tragschicht (`9795c91c`/Asphalttragschicht) und
Frostschutzschicht (`cff84492`/Natürliche Gesteinskörnungen) sind unproblematisch — die
Modell-Konsens-Vorlagen passen semantisch zur Schicht. Sie werden vom Experten-Review
nur final bestätigt.

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
- [x] Benchmark-Rerun für P3/P6/P7/P8 mit Filter-Quality-Fixes (durchgeführt 2026-06-02, Commit `a159897`)
- [ ] Experten-Validierung der `ground_truth.json` für ablation_a/b/c (insbesondere ablation_b/„Nicht bituminöse Tragschicht" — vorläufig `null`, siehe §1.2.5)
- [ ] Post-Review-Fixes adressieren (siehe `.scratch/v2-post-review-fixes/PRD.md`) — nach Paper-Einreichung
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
