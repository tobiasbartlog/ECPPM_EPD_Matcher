# Review-Report — `main(2).tex` (ECPPM/EC³ 2026 Full Paper)

**Erstellt:** 2026-06-05
**Basis:** Vollständige Durchsicht von `main(2).tex` + `EPD_Matcher(1).bib`, gegengeprüft gegen `docs/studie/paper_design.md` (Stand 2026-06-05) und die Projekt-Notizen.
**Zeilenangaben** beziehen sich auf `main(2).tex` in der Fassung, die mir vorlag. Da nach Abschnitt-A-Fixes Zeilen verrutschen können, ist jeweils ein wörtliches Kurzzitat angegeben.

**Scope-Hinweis:** Abschnitt **A** (kaputte `\cite`-Keys, doppelter `Chen.2024`-Bib-Eintrag, `llrcccc`-Tabellenspalte, Müll nach `\end{document}`) ist laut Absprache **bereits erledigt** und hier weggelassen.

**Vorab — was gut ist und nicht angefasst werden sollte:** Sämtliche Kernzahlen sind konsistent mit `paper_design.md`: Tab. 3 (Top-1/Top-3), Tab. 4 (Tokens/Kosten), die Token-Faktoren (164×, 349×, ~5×), die Kostenreduktionen (99,4 % / 97,7 % / 98,3 %), die Whitelist-Arithmetik (6+35+278 = 319 ≈ 11,5 % von 2779) und die Migrationstabelle (268/280, 168/180, 100/100, 88/100). Diese Stellen sind belastbar.

---

## Inhaltsübersicht

- **B — Sachliche Fehler / falsche oder inkonsistente Zahlen** (B1–B4)
- **C — Fehlende Inhalte / offene Reviewer-Punkte** (C1–C10)
- **D — Argumentation härten** (D1–D6)
- **E — Sprache / Stil / Typos** (kompakt)
- **F — Zu verifizieren** (kein Defekt, nur Gegencheck)
- **Priorisierte Checkliste**

---

## B — Sachliche Fehler / falsche oder inkonsistente Zahlen

### B1 — „twelve pairwise comparisons … eleven cases" ist falsch (es sind 16/15)

**Zitat** (`main.tex:475–479`):
> „Across all **twelve** pairwise comparisons in which NamePref is added to an otherwise identical configuration, accuracy decreases in **eleven** cases---for example $P3\rightarrow P6$ ($-6.7$ to $-21.7$\,pp) and $P7\rightarrow P8$ ($-16.3$ to $-21.7$\,pp)---with a single small improvement (gpt-5-chat, $P1\rightarrow P4$, $+6.0$\,pp)."

Wiederholt in der Diskussion (`main.tex:619–620`):
> „its effect is isolated by the **eleven-of-twelve** accuracy decreases reported in the results."

**Warum problematisch:** NamePref wird in **vier** Config-Paaren hinzugefügt (P1→P4, **P2→P5**, P3→P6, P7→P8), jeweils über **vier** Modelle = **16** paarweise Vergleiche, nicht zwölf. Offenbar wurde das Batch-Paar P2→P5 weggelassen. Das ist doppelt ungünstig: erstens ist es ein nachrechenbarer Zählfehler (ein Reviewer prüft genau das an deiner eigenen Tabelle nach), zweitens **verschenkst du dein eigenes Ergebnis** — P2→P5 fällt durchgängig, die korrekte Aussage (15 von 16) ist *stärker* als die behauptete (11 von 12).

Nachrechnung aller 16 Differenzen (P_NamePref-ON − P_NamePref-OFF, in pp):

| Paar | 4o-mini | 5-chat | 5-nano | 5.2-chat |
|------|--------:|-------:|-------:|---------:|
| P1→P4 | −10,6 | **+6,0** | −29,6 | −23,0 |
| P2→P5 | −29,3 | −12,0 | −9,4 | −15,0 |
| P3→P6 | −6,7 | −21,7 | −19,0 | −12,6 |
| P7→P8 | −16,3 | −18,6 | −21,3 | −21,7 |

→ **15 Rückgänge, 1 Verbesserung** (gpt-5-chat, P1→P4, +6,0). Die im Text genannten Spannen „−6,7 bis −21,7" (P3→P6) und „−16,3 bis −21,7" (P7→P8) stimmen — nur die Gesamtzahl nicht.

**Vorschlag** (Results, paste-ready):
> „Across all **sixteen** pairwise comparisons in which NamePref is added to an otherwise identical configuration (the four config pairs P1→P4, P2→P5, P3→P6 and P7→P8, each across four models), accuracy decreases in **fifteen** cases---for example $P3\rightarrow P6$ ($-6.7$ to $-21.7$\,pp) and $P7\rightarrow P8$ ($-16.3$ to $-21.7$\,pp)---with a single small improvement (gpt-5-chat, $P1\rightarrow P4$, $+6.0$\,pp)."

Und Diskussion: „… isolated by the **fifteen-of-sixteen** accuracy decreases reported in the results."

---

### B2 — „slightly lower" für gpt-5.2-chat (−20,4 pp) ist beschönigend

**Zitat** (`main.tex:464–467`):
> „enabling it alone (P3) raises gpt-4o-mini from 29.3\,\% to 77.0\,\% and gpt-5-chat from 67.3\,\% to 85.0\,\%, while it leaves the stronger models **slightly lower** (gpt-5-nano $85.3\rightarrow82.7$\,\%, gpt-5.2-chat $98.7\rightarrow78.3$\,\%)."

**Warum problematisch:** Für gpt-5-nano ist −2,6 pp tatsächlich „slightly". Für gpt-5.2-chat sind es **−20,4 pp** — das ist der größte negative Filtereffekt im ganzen Datensatz und wird hier verbal kleingeredet. Ein Reviewer liest die Zahl, sieht „slightly" und wertet das als selektive Darstellung. Du erklärst den Effekt in der Diskussion (`:599–602`) ohnehin sauber („aggressive candidate reduction can remove a borderline-correct EPD") — dann sollte der Results-Teil ihn nicht verharmlosen, sondern neutral benennen.

**Vorschlag:**
> „… while it leaves gpt-5-nano essentially unchanged ($85.3\rightarrow82.7$\,\%) and **lowers the strongest model, gpt-5.2-chat, more markedly** ($98.7\rightarrow78.3$\,\%, $-20.4$\,pp)---a trade-off we examine in the discussion."

---

### B3 — Migrations-Experiment: „(120 runs)" passt nicht zu „four models … three inputs … five repetitions"

**Zitat** (`main.tex:546–549`):
> „The experiment ran at the P7 operating point over **four models and three inputs with five repetitions (120 runs)**, measuring the migration rate …"

**Warum problematisch:** 4 × 3 × 5 = **60**, nicht 120. Die 120 ergeben sich nur, wenn man **beide Arme** (Vorher = `local`, Nachher = `local-custom`) zählt — das steht hier aber nicht. Gleichzeitig nennt Tab. 5 den Nenner **280** („268/280"), was *Layer-Outcomes im Nachher-Arm* sind (60 Runs × 5 Layer − 20 Null-Layer = 280). Ein Leser, der „120 runs" sieht und dann „268/280" liest, kann die Buchhaltung nicht nachvollziehen. (Anmerkung: dieselbe `4×3×5=120`-Arithmetik steht auch in `paper_design.md` §5 und ist dort schon falsch — Quelle des Fehlers.)

**Vorschlag:**
> „The experiment ran at the P7 operating point over four models, three inputs and five repetitions in a **before/after design** (generic catalogue vs.\ catalogue augmented with the nine entries), i.e.\ **60 runs per arm, 120 runs in total**. Migration is evaluated on the after arm, yielding **280 layer-level matches** (the single null-reference layer of Input~B excluded; cf.\ Sec.~\ref{...})."

---

### B4 — Widersprüchliches Preisdatum (B-Rest aus Abschnitt A; rein inhaltlich)

**Zitat 1** (`main.tex:411`): „model-specific token prices are recorded as of **05.06.2026**\@."
**Zitat 2** (`main.tex:668`): „Azure list prices (Sweden Central, Global Standard, **[01.06.2026]**) …"

**Warum problematisch:** Zwei verschiedene Stichdaten für dieselbe Preisbasis (05.06. vs. 01.06.), und in `:668` stehen noch **Platzhalter-Klammern** `[...]`. `paper_design.md` §3.4 schlug zudem „May 2026" vor — drei Varianten insgesamt. Da das gesamte Kosten-Argument auf einem klar datierten Preisstand beruht (und du das als Limitation explizit machst), muss das Datum an allen Stellen identisch und ohne Klammern sein.

**Vorschlag:** Ein Datum festlegen (empfohlen: das Datum des tatsächlichen Preisabrufs für die v2-Läufe) und an beiden Stellen wörtlich gleich schreiben, Klammern entfernen. Falls noch offen → `paper_design.md` §6 TODO „Preisdatum der 4 Azure-Modelle dokumentieren" zuerst schließen.

---

## C — Fehlende Inhalte / offene Reviewer-Punkte

> Alle folgenden Punkte stehen z. T. bereits als offene TODOs in `paper_design.md` §6/§7 und sind im Paper **noch nicht umgesetzt**.

### C1 — Kein Prompt-Beispiel (Reviewer 2 hat explizit danach gefragt)

**Zitat** (`main.tex:274–283`, Stage 4): die Prompt-Zusammensetzung wird nur in Prosa beschrieben („The prompt comprises the material designation and layer context, the candidate EPD entries … and an output-format specification (JSON …)").

**Warum problematisch:** Reviewer 2 verlangte wörtlich „How was the prompt designed? An example would support the reader" (`paper_design.md` §4.2, §7 — Status TODO). Eine reine Prosabeschreibung adressiert diese Kritik nicht. Bei einem LLM-Methodik-Paper ist ein abgesetztes Prompt-Beispiel quasi Standard.

**Vorschlag:** Ein gekürztes, echtes Prompt-Listing aus `matching/prompt_builder.py` einfügen (System-Prompt-Kopf, ein Kandidaten-Eintrag exemplarisch, Output-Schema). Paste-ready Gerüst (braucht `\usepackage{listings}`):
```latex
\begin{figure}[htbp]
\begin{lstlisting}[basicstyle=\scriptsize\ttfamily,frame=single,
                   caption={Condensed matching prompt (batch mode).
                            Candidate list truncated.},label={fig:prompt}]
SYSTEM: You match road-construction layers to EPDs ...
        Rules: (1) prefer same layer term; (2) a bituminous
        layer must map to an asphalt EPD; ...
        Return JSON: [{layer, id, confidence, begruendung}]
USER:   Layer 1  NAME="Deckschicht"  MATERIAL="SMA 11 S"
        Candidates:
          d24a85e3 | Splittmastixasphalt (SMA) | <techn. descr.> | <notes>
          85e76e87 | Asphaltbinder | ...
        ...
\end{lstlisting}
\end{figure}
```
Den realen Wortlaut aus dem Code ziehen, nicht erfinden.

---

### C2 — Keine einzige Abbildung im gesamten Paper (Reviewer 1: „Architektur + Diagramm")

**Befund:** Im gesamten Dokument gibt es **kein** `\includegraphics` und keine Figure-Umgebung — nur fünf Tabellen.

**Warum problematisch:** Reviewer 1 forderte „Bessere Beschreibung + Diagramm" der Tool-Architektur (`paper_design.md` §7, Status TODO). Ein 5-Stufen-Pipeline-Paper ohne Pipeline-/Architekturdiagramm ist die auffälligste visuelle Lücke und nahezu sichere Reviewer-Beanstandung. Das Diagramm macht außerdem die drei Ablations-Schalter (Batch/Filter/NamePref) und ihre Wirkorte auf einen Blick verständlich — was den Methodikteil entlastet.

**Vorschlag:** Ein Pipeline-Diagramm (Stage 1–5) mit den drei Toggles als markierte Schaltpunkte. Minimal-Gerüst (TikZ, braucht `\usepackage{tikz}`):
```latex
\begin{figure}[htbp]\centering
\begin{tikzpicture}[node distance=4mm,
  stage/.style={draw,rounded corners,align=center,font=\scriptsize,
                minimum height=8mm,text width=20mm}]
  \node[stage](s1){1. Context\\extraction};
  \node[stage,right=of s1](s2){2. Code\\parsing};
  \node[stage,right=of s2](s3){3. EPD\\pre-filter};
  \node[stage,right=of s3](s4){4. LLM\\matching};
  \node[stage,right=of s4](s5){5. Conf.\\validation};
  \foreach \a/\b in {s1/s2,s2/s3,s3/s4,s4/s5}\draw[->](\a)--(\b);
  % Toggles
  \node[font=\tiny,below=1mm of s1]{NamePref};
  \node[font=\tiny,below=1mm of s3]{Filter};
  \node[font=\tiny,below=1mm of s4]{Batch};
\end{tikzpicture}
\caption{Five-stage matching pipeline. Stages~1, 3 and~4 expose the
         binary switches evaluated in the ablation; stages~2 and~5 are
         held constant.}
\label{fig:pipeline}
\end{figure}
```
Alternativ als externe Vektorgrafik via `\includegraphics`. Falls Platz knapp wird (6–8 Seiten): das Diagramm ersetzt einen Teil der Prosa in `:236–295`.

---

### C3 — Metriken werden im Methodikteil nicht definiert (Top-1, Top-3, Cost-at-Threshold)

**Zitat** (`main.tex:431`): „Table~\ref{tab:acc} reports the primary metric (**mean Top-1 accuracy**) …" — die Definition selbst fehlt. „Under the **cost-at-threshold metric** …" (`:492`) taucht ohne vorherige Definition auf. „Top-3" wird in Tab. 3, im Caption und in der Diskussion (`:631`) benutzt, aber nirgends im Methodikteil definiert.

**Warum problematisch:** Drei Punkte zugleich:
1. **Top-1/Top-3 undefiniert:** Der Leser muss sich die Definition aus Caption + Diskussion zusammensuchen.
2. **Top-3-Caveat fehlt an der richtigen Stelle:** Der entscheidende Hinweis „GT among the top-3 *exported suggestions*, **not** recall@3" (`paper_design.md` §3.1.1) steht nur spät in der Diskussion (`:633–635`). Ohne ihn liest ein Reviewer Top-3 als aufgeblähten Recall@3-Wert über den ganzen Katalog. Das ist genau das „Metrik unbegründet"-Risiko (Reviewer 2).
3. **Cost-at-Threshold undefiniert:** Reviewer 2 hatte den *alten* Cost-Efficiency-Score als „not plausible" abgelehnt. Der neue Cost-at-Threshold muss explizit definiert sein, damit erkennbar wird, dass die Kritik adressiert ist — sonst wirkt es wie derselbe Score unter neuem Namen.

**Vorschlag:** Einen Absatz „Metrics" in §Analysis methods einfügen (paste-ready):
> „We report three metrics. **Top-1 accuracy** is the share of evaluated layers whose highest-ranked suggestion equals the ground-truth EPD, averaged over the five repetitions and the evaluated layers of all three inputs. **Top-3 accuracy** is the share for which the ground-truth EPD appears among the **three highest-ranked *exported* suggestions**; because the tool exports only its five highest-ranked candidates per layer (and the filter reduces the asphalt candidate set to $\approx$5), this is a human-in-the-loop measure of the surfaced shortlist, **not** recall@3 over the catalogue. **Cost-at-threshold** compares, among all configurations that reach **at least** the P1 (baseline) Top-1 accuracy, the mean USD cost per run; the threshold is taken from the measured P1 runs rather than fixed a priori."

---

### C4 — Modell-Deployments werden „in Tabelle gelistet" behauptet, sind es aber nicht

**Zitat** (`main.tex:410–411`): „The **four LLM deployments are listed in Table~\ref{tab:acc}**; model-specific token prices are recorded as of 05.06.2026."

**Warum problematisch:** Tab. 3 enthält nur Kurz-Header (`4o-mini`, `5-chat`, `5-nano`, `5.2-chat`) — **keine** Deployment-/Versionsnamen, kein Kontextfenster, **keine Preise**. Die „model-specific token prices" werden mehrfach referenziert (Kostenargument, Limitation), aber nirgends tabelliert. Das ist eine offene Referenz auf nicht vorhandene Information und unterläuft das zentrale Kosten-Narrativ und die Reproduzierbarkeit.

**Vorschlag:** Eine kleine Modelltabelle ergänzen (Werte aus deinem Preisabruf einsetzen — nicht erfunden):
```latex
\begin{table}[htbp]
  \caption{Evaluated Azure OpenAI deployments and list prices
           (Sweden Central, Global Standard, <DATUM>).}
  \label{tab:models}
  \centering\small
  \begin{tabular}{lccc}
    \toprule
    \textbf{Short name} & \textbf{Deployment / version} &
    \textbf{In \$/1M} & \textbf{Out \$/1M} \\
    \midrule
    4o-mini  & gpt-4o-mini (<ver>)  & <..> & <..> \\
    5-chat   & gpt-5-chat (<ver>)   & <..> & <..> \\
    5-nano   & gpt-5-nano (<ver>)   & <..> & <..> \\
    5.2-chat & gpt-5.2-chat (<ver>) & <..> & <..> \\
    \bottomrule
  \end{tabular}
\end{table}
```
Und `:410` umformulieren auf „… are listed in Table~\ref{tab:models}".

---

### C5 — Keine Streuungsmaße, obwohl die 5 Repetitionen mit „Varianz" begründet werden

**Zitat** (`main.tex:406–408`): „repeated five times … Repetition **increases the statistical power** of the analysis and enables a **reliable estimation of performance variance** across configurations."

**Warum problematisch:** Du begründest die Replikation ausdrücklich mit Varianzschätzung, berichtest dann aber in Tab. 3/4 und im Text **ausschließlich Mittelwerte** — keine SD, kein CI, kein min/max, kein Signifikanztest. Ein methodisch orientierter Reviewer (R2) hakt hier sicher ein: „Varianz als Begründung genannt, aber nie gezeigt." Auch Aussagen wie „P7 ist die beste Config" oder der NamePref-Effekt bleiben ohne Streuung schwer einzuordnen (sind 90,3 vs. 91,7 unterscheidbar?).

**Vorschlag:** Mindestens eines davon ergänzen (Rohdaten liegen vor — `top_matches` je Schicht/Rep):
- SD oder min–max über die 5 Reps für die Kern-Configs (P1, P3, P7) als zusätzliche Zeile/Spalte oder im Fließtext;
- **oder** ein einfacher Signifikanztest für die zwei Headline-Claims (P7 vs. P1; NamePref-Effekt), z. B. McNemar auf Layer-Ebene oder ein Bootstrap-CI über die Reps.
Formulierungszusatz in §Analysis methods: „Across repetitions we report the mean and, for the principal comparisons, the standard deviation; differences are tested with …".

---

### C6 — ÖKOBAUDAT-Snapshot (Stand/Stock) nicht genannt

**Zitat** (`main.tex:539–540`): „The preceding results assume the **current ÖKOBAUDAT catalogue** …"; „2779 catalogue EPDs" (`:350`).

**Warum problematisch:** „Current" + eine Anzahl ohne Datum/Stock-Version ist nicht reproduzierbar — und Reproduzierbarkeit ist dein erklärtes Ziel (Abstract, Objectives). `paper_design.md` (Projektnotiz) hält fest: Stock = `OBD_2024_I`, 2779 EPDs nach Dedup. Das gehört ins Paper. Offener TODO in §6.

**Vorschlag:** In §Research design oder §EPD pre-filter einen Satz: „All runs use a local SQLite snapshot of ÖKOBAUDAT, stock **OBD\_2024\_I** (2{,}779 deduplicated EPDs, retrieved <DATUM>), so that all 480 runs query an identical database state."

---

### C7 — LLM-Temperature / Seed / Determinismus nicht berichtet

**Befund:** Die einzige Aussage zur Stochastik ist „identical inputs can produce varying outputs under the inherent stochasticity of LLM-based matching" (`:405–406`). Es fehlt der Sampling-Parameter (Temperature/top-p) und ob Seeds fixiert waren.

**Warum problematisch:** Ein „reproducible evaluation framework" (Objectives, `:169`; Conclusion) ohne Angabe der Decodierungs-Parameter ist angreifbar — die Reproduzierbarkeit hängt direkt daran. Auch die Interpretation der Varianz (C5) braucht den Temperature-Kontext.

**Vorschlag:** Einen Satz in §Research design/§Analysis methods: „All deployments were queried at temperature $=<x>$ (default sampling, no fixed seed), which is the source of the run-to-run variation motivating the five repetitions." Werte aus `config/settings.py` / dem API-Call übernehmen.

---

### C8 — Schlüssel-Normen unzitiert (RStO, TL Asphalt-StB, ISO 14025)

**Zitat:** „the designation in the \texttt{NAME} field follows **RStO** nomenclature" (`:221`); „German asphalt designations follow the nomenclature defined in **TL Asphalt-StB 07/13**" (`:256`); EPD wird im Abstract/Intro eingeführt, ohne ISO 14025 zu nennen.

**Warum problematisch:**
- **RStO**: wird ≥3× als normative Grundlage genannt, aber **nie zitiert** — obwohl der Bib-Eintrag `ForschungsgesellschaftfurStraenundVerkehrswesene.V..2024` („RStO 12/24") existiert.
- **TL Asphalt-StB**: ist die zentrale Norm für Stage 2, hat aber **gar keinen Bib-Eintrag**. Eine zentrale, mehrfach referenzierte Norm ohne Quelle ist eine klare Lücke (R2 mahnte fehlende Refs an).
- **ISO 14025** (Type III EPD): Bib-Eintrag `InternationalOrganizationforStandardization.2006` vorhanden, aber EPD wird ohne Normbezug definiert.

**Vorschlag:** (1) RStO an erster Nennung (`:221`) zitieren; (2) TL Asphalt-StB als `@misc`/`@techreport` in die `.bib` aufnehmen und an `:256` zitieren; (3) bei der ersten EPD-Definition ISO 14025 zitieren. Beispiel-Bib für TL Asphalt-StB:
```bibtex
@misc{TLAsphaltStB.2013,
  author = {{Forschungsgesellschaft f\"ur Stra\ss en- und Verkehrswesen e.V.}},
  year   = {2013},
  title  = {Technische Lieferbedingungen f\"ur Asphaltmischgut f\"ur den
            Bau von Verkehrsfl\"achenbefestigungen (TL Asphalt-StB 07/13)},
  address= {K\"oln}, publisher = {FGSV Verlag}
}
```

---

### C9 — IFC→`input.json`-Extraktion nicht beschrieben (venue-kritisch)

**Zitat** (`main.tex:219–223`): „we derive three input scenarios (A, B, C) from the layer structure of this model … the designation in the \texttt{NAME} field follows RStO nomenclature … The inputs differ only in the engineer-written \texttt{MATERIAL} specification …"

**Warum problematisch:** Die Pipeline startet faktisch bei der JSON; *wie* `NAME`/`MATERIAL` aus dem IFC-Modell gewonnen werden (welche PSets/Attribute, manuell vs. automatisiert), steht nirgends. Bei einer **IFC-fokussierten** Konferenz (ECPPM) ist genau dieser Schritt für die Community zentral, und R1 wollte „IFC-Datenqualität Straßen" stärker im Background. So wirkt das IFC im Titel/Abstract stärker eingebunden, als es der Methodenteil belegt.

**Vorschlag:** 2–3 Sätze in §Research design: aus welchem IFC-Entity-/PSet-Feld `NAME` und `MATERIAL` stammen (z. B. `IfcMaterialLayer.Name`, Pset-Property X), ob die Extraktion manuell oder über einen IFC-Parser erfolgte, und welche Inkonsistenzen dabei real auftraten (verbindet sich mit dem „copy-paste error"-Layer in `:534`). Das schließt zugleich R1's Background-Kritik.

---

### C10 — Reproduzierbarkeit: kein Code-/Daten-Verfügbarkeits-Statement

**Befund:** Das Paper verspricht ein „reproducible evaluation framework", nennt aber kein Repository, keinen Daten-/Artefakt-Link und keinen Verfügbarkeits-Hinweis (Code, Ground-Truth-JSONs, Run-Rohdaten).

**Warum problematisch:** „Reproducible" ohne Artefaktzugang ist eine schwache Behauptung; viele Reviewer erwarten inzwischen ein Availability-Statement. Für Blind Review anonymisiert möglich.

**Vorschlag:** Kurzer Satz am Ende (Conclusion oder eigenes „Data availability"): „Code, input scenarios, ground-truth labels and run-level results will be released upon publication (anonymised repository: <link>)." Falls eine Freigabe nicht möglich ist, zumindest beschreiben, welche Artefakte existieren (z. B. `ablation_analysis.xlsx`).

---

## D — Argumentation härten (kein Fehler, aber angreifbar)

### D1 — Migrations-Experiment: Zirkularitäts-Caveat im Paper unvollständig

**Zitat** (`main.tex:550–551`): „retaining the incumbent generic EPD should not necessarily be interpreted as an incorrect match …"

**Warum problematisch:** Die custom-Einträge sind per Konstruktion whitelist-konform **und** als besserer Match modelliert; dann wird die Migration zu ihnen gemessen. `paper_design.md` §5/§5.0 framed das bewusst eng („Mechanismus, nicht Coverage; kein Beweis"), aber im Paper fehlt der **entscheidende Glaubwürdigkeitssatz**: dass jeder Eintrag auf ein **real publiziertes Produkt-EPD** modelliert ist (Anti-Fabrikations-Guardrail; NEPDs von Peab/Colas/Velde/Franzefoss). Ohne den wirkt das Experiment wie eine selbst gelegte Lücke.

**Vorschlag:** In §Sensitivity einen Satz ergänzen: „Each of the nine entries was modelled on a **real, published product declaration** (EPD-Norge/manufacturer NEPDs for SMA, asphalt binder, base course and crushed aggregate) and constrained to a whitelist-conformant classification; we report the **migration rate** (generic → product-specific) rather than treating the custom entry as ground truth, to avoid a circular self-set target." Optional die NORSUS-Variabilität (11,3–83,1 kg CO₂e/t, bereits in `:158–160` zitiert) hier als „warum Migration LCA-relevant ist" rückkoppeln.

---

### D2 — gpt-5-nano-„collapse" unter Batch: Erklärung ignoriert, dass der Filter ihn auffängt

**Zitat** (`main.tex:467–470` und `:608–611`): „Batching alone~(P2) … sharply degrades gpt-5-nano ($85.3\rightarrow31.7$\,\%), indicating that this model is sensitive to producing structured output for all layers in a single response."

**Warum problematisch:** Die Erklärung „empfindlich bei strukturiertem Output für alle Layer" ist unvollständig, weil **P7 (ebenfalls Batch)** nano auf **74,0 %** zurückholt. Der Kollaps tritt also nur bei Batch **über dem ungefilterten Riesenkatalog** auf — es ist ein Batch-×-Kontextlängen-Effekt, nicht Batch an sich. So wie formuliert, widerspricht die Erklärung der eigenen P7-Zahl und lädt zur Nachfrage ein.

**Vorschlag:** Den mildernden Befund ergänzen: „This degradation is specific to batching over the **unfiltered** catalogue: once pre-filtering shrinks the candidate set, batching no longer harms gpt-5-nano (P7: 74.0\,\%), indicating that the failure mode is the combination of batch decoding **and** a very long candidate context rather than batching itself."

---

### D3 — „Stage 2 largely inert" steht in Spannung zum filtertragenden Asphalt-Parsing

**Zitat** (`main.tex:666–667`): „renders **material-code parsing (Stage~2) largely inert** in the current catalogue."; vgl. `:262–265` „its contribution is bounded by catalogue granularity … the switch is held constant".

**Warum problematisch:** Stage 2 liefert das `ist_asphalt`-Fakt, auf dem Fall 1 des Filters (Asphalt-Zweig) überhaupt beruht. „Inert" suggeriert „tut nichts", obwohl das Parsing für den Filter **funktional notwendig** ist. Ein aufmerksamer Reviewer fragt: „Wenn Stage 2 inert ist, wie erkennt der Filter dann Asphalt?"

**Vorschlag:** Präzisieren auf „accuracy-inert", nicht „funktionslos": „Stage~2 still drives the asphalt branch of the pre-filter, but in the current catalogue it yields **no additional matching accuracy**, because no product-specific infrastructure EPDs exist for its parsed codes to resolve to; its accuracy contribution---not its function---is therefore bounded by catalogue granularity." (Verbindet sich sauber mit dem Migrations-Experiment, das genau zeigt, wie Stage 2 „reaktiviert" wird, sobald spezifische EPDs vorliegen.)

---

### D4 — Neuheitsabgrenzung zu Petrosa et al. zu diffus (Reviewer 1)

**Zitat** (`main.tex:195`, Related Work): ausführliche, faire Beschreibung von Petrosa et al. (ÖKOBAUDAT, LLM, Python, semi-/vollautomatisch).

**Warum problematisch:** Petrosa et al. ist die **nächstgelegene Vorarbeit** — gleiche Datenbank, gleicher LLM-Ansatz, gleiche Sprache. R1 mahnte fehlende „Neuheitsabgrenzung" an (`paper_design.md` §7). Der Delta (Straßeninfrastruktur-Fokus, domänenspezifischer Vorfilter mit TL-Asphalt-StB-Nomenklatur, **vollfaktorielle** Ablation, explizite Cost-at-Threshold-Analyse) steht verstreut, aber nirgends als ein klarer Kontrastsatz. Ohne den droht das „inkrementell"-Urteil.

**Vorschlag:** Am Ende des Related-Work-Absatzes (oder Beginn Methodik) einen expliziten Kontrast: „Unlike Petrosa et al., who target building-focused ÖKOBAUDAT matching with a general-purpose LLM, we (i) specialise the pipeline to **road-infrastructure** nomenclature (TL Asphalt-StB / RStO), (ii) introduce a **rule-based civil-engineering pre-filter** as an explicit, ablatable stage, and (iii) evaluate the design with a **full-factorial ablation** that exposes accuracy–cost interactions rather than a single configuration."

---

### D5 — Abstract nennt kein quantitatives Kernergebnis

**Zitat** (`main.tex:121`): „Results **quantify accuracy–cost trade-offs** and demonstrate the pipeline's readiness to scale as BIM adoption advances and EPD coverage expands."

**Warum problematisch:** Das ist ein „results-free" Schlusssatz. In diesem Feld erwartet man im Abstract die Headline-Zahl. Du hast eine starke: bis ~99 % Kostenreduktion bei gehaltener/gesteigerter Accuracy für kostensensitive Modelle, plus Top-3 >95 % unter P7. Ohne Zahl wirkt der Abstract schwächer als das Paper ist.

**Vorschlag:** „Across 480 runs, domain-specific pre-filtering reduces inference cost by up to **99\,\%** while **raising** accuracy for cost-sensitive models (gpt-4o-mini: 29\,\%→77\,\%), and the recommended batch+filter configuration places the correct EPD among the top-3 surfaced candidates in **>95\,\%** of cases for three of four models."

---

### D6 — Konferenz-/Template-Konsistenz prüfen (ECPPM vs. EC³)

**Zitat:** Template-Kopf „**ECPPM 2026** … Cardiff … 9–11 September 2026" (`:1–8`); Diskussion „For the **ECPPM community**" (`:642`). `paper_design.md` nennt durchgängig „**EC³ 2026**, Corfu, Juli".

**Warum problematisch:** ECPPM (Product & Process Modelling) und EC³ (Computing in Construction) sind **verschiedene** Konferenzen mit unterschiedlichen Templates/Terminen. Das Paper selbst ist intern konsistent (ECPPM), aber das Design-Doc widerspricht — vermutlich ist das Doc veraltet. Falls doch EC³ das Ziel ist, stimmt die **Formatvorlage nicht**.

**Vorschlag:** Zielkonferenz bestätigen. Wenn ECPPM korrekt: nichts am Paper, aber `paper_design.md` §Kontext aktualisieren (sonst irritiert es spätere Mitautoren). Wenn EC³: Template/Termin/„ECPPM community" anpassen.

---

## E — Sprache / Stil / Typos (kompakt)

| Stelle | Zitat | Problem | Vorschlag |
|--------|-------|---------|-----------|
| `:146` | „highlighting the need **methods** that enable" | fehlendes „for" | „the need **for** methods" |
| `:189` | „the **feasability** of EPD matching" | Tippfehler | „feasibility" |
| `:228` | „Input~B: industry model, alternative asphalt mixtures to test robustness …" | Satzfragment, stilistisch uneinheitlich zu A und C (Vollsätze) | „Input~B replicates an industry model with alternative asphalt mixtures, testing robustness against non-standard designations." |
| `:324` | „(English: mineral building materials / asphalt,**.../** aggregates, and **.../** mortar and concrete / concrete)" | englische Glosse mitten in die deutsche Aufzählung geklemmt; schwer lesbar | Glosse aus dem Fließtext nehmen, die drei Präfixe als kurze Liste/Fußnote mit deutsch + englisch nebeneinander |
| `:435–437` | Caption „…per configuration and model, **Cell** color represents…" | Komma + Großschreibung mitten im Satz | Punkt statt Komma: „… per configuration and model. Cell color represents …" |
| `:525` | „Cost reflects input and output tokens; only input tokens are shown as they are model-independent." | minimal verwirrend (Kosten enthalten Output, Spalte zeigt nur Input) | „The cost columns include both input and output tokens; the token column lists input tokens only, as these are identical across models." |
| durchgängig | mal `\"OKOBAUDAT`, mal „ÖKOBAUDAT" | Konsistenz | einheitliches Makro/Schreibweise |

---

## F — Zu verifizieren (kein Defekt, nur Gegencheck)

- **`:429` „All 480 pipeline runs completed without execution failures."** — Im Pilotlauf (`ablation_20260601_195759`, 96 Runs) gab es laut Projektnotiz 2 Fehler (gpt-5-nano-Crash; JSON-Parse bei gpt-5.2-chat). Der **Paper-Lauf** ist ein anderer (`ablation_20260602_145931`), und `paper_design.md` §1.2.4 vermerkt, dass die zwei zuvor abgebrochenen Runs im neuen Lauf durchliefen. Aussage ist damit *plausibel korrekt* — bitte einmal gegen das Run-Log des finalen 480er-Datensatzes bestätigen, bevor sie so stehen bleibt.
- **Cost-Spaltenreihenfolge in Tab. 4** — Header-Reihenfolge `4o-mini, 5-chat, 5-nano, 5.2-chat` identisch zu Tab. 3; die Per-Modell-Kosten plausibilisiert (nano billig, 5.2-chat teuer). Kurz gegen `cost_tracker`-Export gegenprüfen, dass keine Spalten vertauscht sind (nano↔chat sind in `paper_design.md` §1.2.6 anders sortiert als in §3.1.2 — beide intern konsistent, aber leicht zu verwechseln).

---

## Priorisierte Checkliste

**Muss vor Einreichung (Glaubwürdigkeit/Reviewer-Killer):**
- [ ] B1 — „twelve/eleven" → „sixteen/fifteen" (2 Stellen)
- [ ] B3 — Migrations-„(120 runs)" korrekt aufschlüsseln
- [ ] C1 — Prompt-Beispiel (R2-Forderung)
- [ ] C2 — Pipeline-/Architekturdiagramm (R1-Forderung)
- [ ] C3 — Metrikdefinitionen inkl. Top-3-„not recall@3"- und Cost-at-Threshold-Caveat
- [ ] C5 — Streuung/Signifikanz für Headline-Claims

**Sollte (Härtung/Reproduzierbarkeit):**
- [ ] B2 — „slightly lower" entschärfen (gpt-5.2-chat −20,4 pp)
- [ ] B4 — Preisdatum vereinheitlichen, Platzhalter-Klammern raus
- [ ] C4 — Modelltabelle (Versionen + Preise)
- [ ] C6 — ÖKOBAUDAT-Snapshot (OBD_2024_I + Datum)
- [ ] C7 — Temperature/Seed nennen
- [ ] C8 — RStO/TL Asphalt-StB/ISO 14025 zitieren
- [ ] D1 — Anti-Fabrikations-Satz im Migrations-Abschnitt
- [ ] D4 — Neuheitsabgrenzung zu Petrosa et al.

**Nice-to-have (Politur):**
- [ ] C9 — IFC→JSON-Extraktion beschreiben
- [ ] C10 — Data-availability-Statement
- [ ] D2 — nano-collapse: Filter-Recovery erwähnen
- [ ] D3 — „Stage 2 inert" → „accuracy-inert"
- [ ] D5 — Abstract um Headline-Zahl ergänzen
- [ ] D6 — Venue ECPPM vs. EC³ bestätigen
- [ ] E — Typos/Stil
- [ ] F — zwei Verifikationen

---

*Ende des Reports.*
