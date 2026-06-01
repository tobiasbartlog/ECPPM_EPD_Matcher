Status: ready-for-human

# PRD: Ablationsstudie v2 — Auswertungs-Skript + Custom-Entries-Experiment

## Erledigt

- `benchmark/ablation_benchmark.py` — Benchmark-Runner vollständig implementiert
  (480 Runs, alle 8 Configs, Ground-Truth-Vorlagen, HTML + Excel Rohdaten, Flags, Timestamps)
- `TestInput/ablation_a/b/c/input/input.json` — alle drei Input-JSONs angelegt
- `TestInput/ablation_a/ground_truth_template.json` — aus Mini-Testlauf erzeugt
- `benchmark/ablation_analysis.py` — Auswertungs-Skript vollständig implementiert
  (Accuracy-Berechnung, Cost-at-Threshold, HTML 6 Tabs, Excel 7 Sheets)
- `benchmark/custom_entries_experiment.py` — Custom-Entries-Experiment vollständig implementiert
- `benchmark/custom_entries_config_template.json` — Template für Experiment-Konfiguration

## Offene Schritte (manuelle Arbeit)

1. Vollständige Benchmark-Läufe (480 Runs) ausführen:
   `python benchmark/ablation_benchmark.py`
2. `ground_truth_template.json` pro Input prüfen → als `ground_truth.json` speichern
3. Auswertung ausführen:
   `python benchmark/ablation_analysis.py --runs benchmark_output/ablation_<ts>/benchmark_runs.json`
4. `benchmark/custom_entries_config.json` aus Template erstellen und UUIDs/Felder eintragen
5. Custom-Entries-Experiment ausführen:
   `python benchmark/custom_entries_experiment.py --config benchmark/custom_entries_config.json --baseline-runs <runs.json>`

## Out of Scope

- Änderungen an `main.py`, Glossar-Filter, Pipeline-Komponenten
- Neue Ablations-Schalter (P1–P8 bleibt unverändert)
- Detail-Matching (`EPD_USE_DETAIL_MATCHING=true`)
- Deployment oder Sharing der Webapp auf einem Server
- Open-Source-LLM-Alternativen
