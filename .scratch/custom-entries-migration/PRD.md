# PRD: Custom-Entries-Migrations-Experiment + Top-3-Accuracy

Status: ready-for-agent

---

## Problem Statement

Das v2-Paper muss zwei Reviewer-Punkte adressieren, für die in der aktuellen Auswertung noch
die Datengrundlage fehlt:

**1. „Sparse EPD data not addressed" (Reviewer 1).** Der ÖKOBAUDAT-Snapshot ist für
Infrastruktur so dünn besetzt, dass dieselbe **generische** EPD materiell verschiedene Schichten
matcht: Deckschicht `SMA 11 S`, `SMA 8 S mit PmB` und `Splittmastix lärmreduzierend` kollabieren
alle auf dieselbe Ground-Truth-UUID; ebenso die drei bituminösen Tragschicht-Materialien. Das ist
der **Stage-2-Vorbehalt live in den Daten**: das Material-Code-Parsing (Stage 2) liefert reiche
Struktur, die wirkungslos verpufft, weil kein produktspezifisches EPD existiert. Es fehlt eine
Messung, die zeigt, was passiert, wenn produktspezifische EPDs verfügbar werden — die im Paper
(CPR / Digital Product Passports) als Zukunft argumentiert werden.

**2. „Multiple acceptable labels" / Human-in-the-Loop nicht gemessen (Reviewer 1).** Das Tool
exportiert pro Schicht die fünf höchstgerankten Vorschläge zur manuellen Auswahl, evaluiert wird
aber nur der Top-1-Match. Die strenge Top-1-Accuracy unterzählt damit den praktischen Nutzen: Wenn
die richtige EPD oft auf Platz 2–3 liegt, findet der Bearbeiter sie trotzdem — aber das Paper kann
es derzeit nicht beziffern.

Beide Lücken sind aus dem vorhandenen 480-Run-Datensatz (`ablation_20260602_145931`) bzw. mit
einem kleinen, billigen Zusatzlauf schließbar, ohne die Hauptablation neu zu rechnen.

---

## Solution

Zwei analyse-seitige Erweiterungen, beide an der bestehenden, validierten Ground Truth verankert:

### Lösung 1 — Custom-Entries-Migrations-Experiment

Ein kontrolliertes Vorher/Nachher-Experiment auf einer **isolierten DB-Kopie**: In die Kopie werden
**custom-Einträge** eingefügt, die auf real existierende Produkt-EPDs (IBU, EPD Norge,
Hersteller-EPD) modelliert sind und je einer spezifischen Material-Bezeichnung der Inputs A und B
entsprechen. Gemessen wird die **Migrationsrate** — der Anteil der Läufe, in denen der Top-1-Match
vom generischen Alt-EPD auf den produktspezifischen custom-Eintrag **wechselt**.

Die Claim ist bewusst eng: *Sensitivität gegenüber Datenbankabdeckung* — **kein „Beweis"**. Die
Migrationsrate misst einen Mechanismus („das Modell upgradet auf bessere Daten, sobald sie da
sind"), nicht eine selbstgelegte Lücke. Damit ist die Aussage zirkularitäts-robust: es wird **nicht**
behauptet, der eingefügte Eintrag sei die einzige Wahrheit.

**Drei Input-Arme:**
- **A (Norm-Code)** — sauberstes Migrationssignal.
- **B (Praxis-Code)** — Migration mit real abweichenden Bezeichnungen.
- **C (Freitext, keine Norm-Codes)** — eigenständiger **Freitext-Robustheitsarm**: C bekommt keine
  eigenen custom-Einträge, sondern wird gegen die für A/B eingefügten getestet. Misst, ob das
  NL-Verständnis ausreicht, um auch ohne lexikalische Übereinstimmung zu migrieren, oder ob C auf
  generisch zurückfällt. Beide Ausgänge sind publizierbar.

**Gesplittete Berichterstattung nach Mechanismus:**
- **Asphalt-Schichten (Deck/Binder/bit. Trag)** — *generic-collapse → discrimination* (Hauptbefund).
- **Körnungs-Schichten (Nicht-bit. Trag, Frostschutz)** — *approximate-grading → exact match*
  (Stützbefund; heutige GT trifft die Körnung nur näherungsweise, z.B. GT `Schotter 16/32` vs. Input
  `STSuB 0/45`).

### Lösung 2 — Top-3-Accuracy

Tab. 3 der Hauptablation wird um eine **Top-3-Spalte neben Top-1** erweitert, vollständig aus dem
bestehenden 480-Run-Datensatz berechnet. Definition: Anteil der bewerteten Schichten, in denen die
GT-UUID unter den **drei höchstgerankten exportierten Vorschlägen** liegt — die
**Human-in-the-Loop-Metrik**, nicht Recall@3 über den Katalog.

---

## User Stories

1. Als Paper-Autor möchte ich die Migrationsrate von generischen auf produktspezifische EPDs
   messen, damit ich Reviewer 1's „sparse EPD"-Kritik mit einem kontrollierten Experiment adressieren
   kann.
2. Als Paper-Autor möchte ich, dass die Migrationsmetrik als „Anteil Top-1-Wechsel
   generisch→spezifisch" definiert ist, damit die Aussage nicht zirkulär wird (Kandidat und Antwort
   nicht selbst gelegt).
3. Als Paper-Autor möchte ich das Experiment auf P7 (BatchFilter) fahren, damit die Migration am
   selben Betriebspunkt gezeigt wird, den ich im Paper als besten empfehle.
4. Als Paper-Autor möchte ich die Migration über alle vier Modelle messen, damit die
   Skalierungs-Aussage modell-robust ist.
5. Als Paper-Autor möchte ich fünf Repetitionen pro Kombination, damit die Migrationsrate gegen
   LLM-Stochastik abgesichert ist — konsistent mit der Hauptablation.
6. Als Paper-Autor möchte ich die Ergebnisse nach Asphalt- vs. Körnungs-Schichten gesplittet sehen,
   damit der dramatische Collapse-Effekt nicht mit dem schwächeren Grading-Effekt vermischt wird.
7. Als Paper-Autor möchte ich Input C ohne eigene custom-Einträge gegen die A/B-Einträge testen,
   damit ich zeigen kann, ob Freitext ohne Norm-Code ebenfalls migriert.
8. Als Paper-Autor möchte ich, dass jeder custom-Eintrag auf ein real existierendes Produkt-EPD
   modelliert und die Quelle dokumentiert ist, damit kein Reviewer „erfundene, trivial auffindbare
   EPDs" beanstanden kann.
9. Als Forscher möchte ich, dass das Experiment gegen eine **isolierte DB-Kopie** läuft, damit die
   Original-DB unverändert bleibt und alle 480 Hauptablations-Runs reproduzierbar bleiben.
10. Als Forscher möchte ich, dass die Konfiguration der custom-Einträge **vor dem Lauf** gegen die
    Tiefbau-Scope-Whitelist validiert wird, damit ein nicht-whitelist-konformer Eintrag nicht
    lautlos in P7 herausgefiltert wird und das Experiment unbemerkt entwertet.
11. Als Forscher möchte ich eine klare Fehlermeldung mit Grund, wenn ein custom-Eintrag die Whitelist
    nicht passieren würde, damit ich die `klassifizierung` korrigieren kann, bevor ich Geld für
    LLM-Runs ausgebe.
12. Als Forscher möchte ich, dass das fehlerhafte INSERT-Beispiel im Config-Template
    (`… / Ungebundene Tragschichten / …`) korrigiert wird, damit ich nicht versehentlich einen
    nicht-whitelist-konformen Pfad kopiere.
13. Als Paper-Autor möchte ich eine Migrations-Tabelle pro (Config, Modell, Input, Schicht), damit
    ich pro Schicht sehen kann, ob und wie zuverlässig migriert wurde.
14. Als Paper-Autor möchte ich, dass die Migrations-Tabelle die Kategorien `migrated`,
    `stayed_generic` und `other` unterscheidet, damit ich Nicht-Migration von Fehl-Migration trennen
    kann.
15. Als Paper-Autor möchte ich eine aggregierte Migrationsrate je Mechanismus (Asphalt / Körnung) und
    je Input-Arm (A / B / C), damit ich die Headline-Zahlen direkt ins Paper übernehmen kann.
16. Als Paper-Autor möchte ich die bestehenden P7-Standard-DB-Runs als „Vorher"-Referenz
    quergeprüft sehen, damit ich sicher bin, dass die „Vorher"-Generik nicht durch den neuen Lauf
    driftet.
17. Als LCA-Nutzer (downstream) möchte ich, dass das Experiment zeigt, dass das Tool bei besserer
    Datenlage spezifischere EPDs wählt, damit ich Vertrauen in die zukünftige Genauigkeit habe.
18. Als Paper-Autor möchte ich eine Top-3-Accuracy-Spalte neben Top-1 in Tab. 3, damit ich den
    Human-in-the-Loop-Nutzen beziffern kann.
19. Als Paper-Autor möchte ich, dass Top-3 vollständig aus dem bestehenden 480-Run-Datensatz
    berechnet wird, damit kein teurer Re-Run nötig ist.
20. Als Paper-Autor möchte ich, dass Top-3 als „GT unter den Top-3 der exportierten Vorschläge"
    definiert und nicht als Recall@3 missverstanden wird, damit Reviewer 2 die Metrik nicht als
    unbegründet kassiert.
21. Als Paper-Autor möchte ich, dass Top-3 additiv zu Top-1 bleibt und **nicht** in die
    Cost-at-Threshold-Metrik einfließt, damit „billig" nicht mit „der Mensch findet es schon"
    vermischt wird.
22. Als Paper-Autor möchte ich Top-3 auch in der Per-Schicht- und Per-Input-Auswertung, damit ich
    Near-Miss-Muster pro Schicht erkennen kann.
23. Als AFK-Agent möchte ich, dass die Top-k-Logik aus den beiden inline-Berechnungen in eine
    parametrisierte Funktion extrahiert wird, damit Top-1 und Top-3 dieselbe getestete Logik nutzen.
24. Als AFK-Agent möchte ich, dass der Migrations-Klassifikator eine reine Funktion über
    Vorher-/Nachher-Run-Daten ist, damit ich ihn ohne LLM-Calls und ohne DB isoliert testen kann.
25. Als Wartender des Codes möchte ich, dass die Whitelist-Prüfung die bestehende Whitelist-Konstante
    aus den `matching_rules` wiederverwendet, damit es keine zweite Quelle der Wahrheit gibt.
26. Als Paper-Autor möchte ich, dass die Sonderbehandlung von ablation_b/„Nicht bituminöse
    Tragschicht" (Praxis-Dateneingabefehler, `null`) im Experiment respektiert wird, damit dort kein
    custom-Eintrag für B angelegt und keine sinnlose Migration gemessen wird.

---

## Implementation Decisions

### Modul A — Top-k-Accuracy-Prädikat (deep module)

- Die heute zweifach inline implementierte Top-1-Logik (Run-Ebene und Schicht-Ebene) wird in eine
  **k-parametrisierte, reine Funktion** extrahiert. Signatur (decision-encoding, nicht final):
  `topk_hit(top_matches: list[str], gt_uuid: str, k: int) -> bool`, definiert als
  `gt_uuid in top_matches[:k]`. Robuste Behandlung: leere Liste → `False`, `k > len(top_matches)` →
  kein Indexfehler.
- Die Aggregations-Funktionen berechnen Accuracy für **k ∈ {1, 3}** parallel. Top-1 bleibt
  Primärmetrik, Top-3 wird als zweite Serie geführt.
- **Tab. 3 / Overview-Tabelle / Heatmap / Excel** erhalten je eine zusätzliche Top-3-Spalte bzw.
  -Serie. Scatter, Pareto und **Cost-at-Threshold bleiben unverändert auf Top-1** verankert.
- Datenbasis: vorhandener 480-Run-Datensatz; die gerankte Liste pro Schicht ist bereits persistiert
  (`top_matches` / `id`-Array, absteigend nach validierter Confidence).

### Modul B — Whitelist-Konformitäts-Validator (deep module)

- Reine Prüf-Funktion: gegeben ein custom-Eintrag (bzw. dessen `klassifizierung`), liefert sie
  `(pass: bool, grund: str)`. Ein Eintrag passt, wenn seine `klassifizierung` mit einem der
  Tiefbau-Whitelist-Präfixe **beginnt**.
- **Wiederverwendung statt Duplizierung**: die Präfix-Liste wird aus der bestehenden
  Whitelist-Konstante der `matching_rules` importiert — keine zweite Definition.
- Wird im Orchestrierungs-Skript **fail-fast vor jedem LLM-Run** aufgerufen: schlägt die Validierung
  fehl, bricht das Experiment mit klarer Meldung ab, bevor Kosten entstehen.

### Modul C — Migrations-Klassifikator (deep module)

- Reine Funktion über zwei Run-Datensätze (Vorher = Standard-DB, Nachher = angereicherte DB) plus die
  Menge der eingefügten custom-IDs. Pro (config, model, input, layer) wird der Top-1 vorher und
  nachher bestimmt und klassifiziert:
  - `migrated` — `after_top1 ∈ custom_ids` (vorher kann per Konstruktion nie eine custom-ID sein, da
    diese nur in der angereicherten DB existieren).
  - `stayed_generic` — `after_top1 == before_top1` und `after_top1 ∉ custom_ids`.
  - `other` — alles übrige (Wechsel auf ein anderes generisches EPD, leere Liste, etc.).
- Aggregation über die 5 Repetitionen: das Outcome wird pro Run bestimmt, die **Migrationsrate** ist
  der Anteil `migrated` über die bewerteten Layer-Runs. Pairing erfolgt auf Ebene
  (config, model, input, layer), nicht rep-zu-rep (Repetitionen sind stochastisch).
- Output: Migrations-Tabelle pro (config, model, input, layer) sowie Aggregate je Mechanismus
  (Asphalt / Körnung) und je Input-Arm (A / B / C).
- Für den Freitext-Arm C gilt derselbe Klassifikator: `custom_ids` sind die für A/B angelegten IDs;
  `migrated` in C bedeutet, dass Freitext ohne eigenen Eintrag den spezifischen A/B-Eintrag findet.

### Orchestrierung & Daten (dünne Glue-/Daten-Schicht)

- **Run-Matrix**: P7 (BatchFilter) × 4 Modelle × 3 Inputs × 5 Reps × {vorher, nachher} ≈ 120 Runs,
  ~$1. Das Custom-Entries-Skript fährt beide Seiten in derselben Session gegen die DB-Kopie
  (drift-frei). Die bestehenden P7-Standard-DB-Runs des 480-Datensatzes dienen als Quercheck der
  „Vorher"-Generik.
- **Isolierung**: Original-DB wird kopiert; custom-Einträge nur in die Kopie eingefügt
  (`source='custom'`); die Nachher-Subprozess-Läufe verwenden die Kopie per ENV.
- **custom_entries_config.json** (Daten-Deliverable): ~8–9 Einträge.
  - Asphalt-Schichten (Deck/Binder/bit. Trag): je ein Eintrag für die A- und die B-Bezeichnung,
    `klassifizierung` unter `Mineralische Baustoffe / Asphalt / …`.
  - Körnungs-Schichten (Nicht-bit. Trag, Frostschutz): Einträge mit exakter Körnung,
    `klassifizierung` unter `Mineralische Baustoffe / Zuschläge / …`.
  - **Wrinkle**: ablation_b/„Nicht bituminöse Tragschicht" ist der `null`-Fehler-Layer → dort nur
    A's Eintrag, B ausgenommen.
  - Jeder Eintrag dokumentiert seine reale Vorlage (IBU / EPD Norge / Hersteller) in einem
    Quellen-Feld.
- **Template-Fix**: das fehlerhafte INSERT-Beispiel im Config-Template
  (`… / Ungebundene Tragschichten / Frostschutzschichten`) wird auf einen whitelist-konformen Pfad
  (`Mineralische Baustoffe / Zuschläge / …`) korrigiert.
- Die Migrations-Auswertung wird ins Custom-Entries-Skript verdrahtet (es berichtet heute nur
  Accuracy). Der Migrations-Report wird zusätzlich zur bestehenden Vorher/Nachher-Accuracy
  ausgegeben.

---

## Testing Decisions

**Was einen guten Test ausmacht**: nur externes Verhalten prüfen, nicht die Implementierung. Die zwei
zu testenden Module sind reine Funktionen ohne LLM-Calls, ohne DB, ohne Netzwerk — Input rein,
Output raus. Keine Mocks nötig. Tests beschreiben das *Verhalten* (welcher Input → welche
Klassifikation / welcher Trefferwert), nicht die internen Schritte.

**Modul C — Migrations-Klassifikator (getestet):**
- generisch → spezifisch (custom-ID) ⇒ `migrated`
- generisch → dasselbe generische ⇒ `stayed_generic`
- generisch → anderes generisches (Nicht-custom) ⇒ `other`
- spezifisch nicht im Nachher (LLM wählt anderes) ⇒ `other`
- leere `top_matches` im Nachher ⇒ `other`, kein Crash
- Freitext-Arm C: `after_top1` = ein für A/B angelegter custom-Eintrag ⇒ `migrated`
- Aggregation: gemischte Reps ergeben die korrekte Migrationsrate
- Guard: custom-ID, die in keinem Run auftaucht, bricht die Aggregation nicht

**Modul A — Top-k-Prädikat (getestet):**
- `gt == top_matches[0]`, k=1 ⇒ hit
- `gt` auf Platz 3, k=3 ⇒ hit; k=1 ⇒ miss
- `gt` nicht in Liste ⇒ miss für alle k
- leere Liste ⇒ miss, kein Crash
- `k > len(top_matches)` ⇒ kein Indexfehler
- Aggregation über mehrere Schichten ergibt korrekten Prozentwert

**Modul B — Whitelist-Validator**: **kein** dedizierter Test im Scope dieses PRD (bewusst). Wird als
Glue gegen die bereits getestete Whitelist-Konstante der `matching_rules` gebaut.

**Prior Art**: Die `matching_rules`-Module enthalten bereits einen selbst-ausführbaren
Whitelist-/Bewertungs-Testblock (TIEFBAU-WHITELIST TEST) mit (Input, Erwartung, Begründung)-Tupeln —
dieselbe tabellarische Teststruktur ist die Vorlage für die neuen Tests.

---

## Out of Scope

- **Keine Neuausführung der Hauptablation** (480 Runs). Top-3 wird rein nachträglich berechnet; die
  Code-Fixes aus `.scratch/v2-post-review-fixes/PRD.md` bleiben dort und werden nicht hier
  adressiert.
- **Kein Filter-OFF-Kontrastarm** (P1/P2). Das Experiment läuft nur auf P7. P3 als saubere
  Isolations-Variante (ein Call pro Schicht) ist optionaler Folgeschritt, nur falls Batch-Rauschen
  das Migrationssignal verrauscht.
- **Keine Coverage-Story** („leere Schicht auffüllen"). Es gibt in den aktuellen Inputs kein ehrliches
  Coverage-Ziel; das Experiment ist ausschließlich Discrimination/Quality.
- **Keine neue Ground-Truth-Bestimmung** als zirkuläre Accuracy-gegen-eingefügten-Eintrag. Accuracy
  gegen neu-bestimmte GT höchstens sekundär und mit Caveat; Headline bleibt die Migrationsrate.
- **Keine Open-Source-Modelle**, kein vierter Input, keine Änderung der vier Azure-Deployments.

---

## Further Notes

- Designprotokoll: alle Entscheidungen sind in `docs/studie/paper_design.md` §5 (Experiment) und
  §3.1.1 (Top-3) dokumentiert und bleiben dort die primäre Referenz beim Paper-Schreiben.
- **Zirkularitäts-Designnotiz**: Reale Produkt-EPDs tragen ihre Bezeichnung im Namen; für A/B ist
  Migration daher teils lexikalisch getragen. Das ist akzeptabel und muss im Paper benannt werden —
  **C (Freitext) trägt die Hauptlast des „echten" Verständnis-Nachweises**, da dort keine lexikalische
  Übereinstimmung vorliegt.
- **Paper-Positionierung**: Abschnitt „Sensitivity to Database Coverage" nach der Hauptablation bzw.
  in Diskussion/Future Work. Kernaussage: sobald produktspezifische EPDs vorliegen, migriert der
  Matcher von generischen auf spezifische Treffer und reaktiviert damit Stage 2.
- **Caveat Top-3 bei Filter=ON**: Kandidatensatz ist klein (~5), Top-3 ist ein „3 von 5"-Maß — bildet
  aber exakt die Nutzersicht ab. Im Paper als „top-3 of the exported suggestions" benennen.
