# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

Copy the `readme` file to `.env` and fill in the required values before running anything:

```
AZURE_OPENAI_API_KEY=...
ENDPOINT_URL=...
ONLINE_EPD_API_BASE_URL=...
ONLINE_EPD_API_USERNAME=...
ONLINE_EPD_API_PASSWORT=...
```

Dependencies (install via pip): `openai`, `python-dotenv`, `requests`

## Running

**Main matcher** — processes a folder containing `input/input.json`, writes `output/output.json`:

```bash
python main.py <id_folder>
# e.g.
python main.py TestInput/id_aufruf_benutzer
```

Flags: `--input-file <name>`, `--output-file <name>`, `--no-batch` (per-material mode instead of one request for all layers).

**Benchmark** — compares multiple Azure deployments against each other:

```bash
python benchmark.py <id_folder> [--models gpt-4o-mini gpt-5-nano ...]
```

**Benchmark analysis** — reads an existing benchmark output folder and produces a comparison report:

```bash
python benchmark_analyze.py <benchmark_output_folder>
```

**Test the filter/validator in isolation:**

```bash
python matching/epd_filter.py
```

## Architecture: 5-stage pipeline

Every matching run passes through these stages (each can be toggled via `.env`):

| Stage | Module | What it does |
|---|---|---|
| 1 — Context extraction | `main.py` | Reads `Gruppen[].NAME` and `MATERIAL` from input JSON; decides which field is authoritative (`EPD_PREFER_NAME_FIELD`) |
| 2 — Material code parsing | `utils/asphalt_glossar.py` | Parses German asphalt codes (e.g. `AC 16 B S`) into structured fields: type, layer, stress class |
| 3 — EPD pre-filtering | `matching/epd_filter.py` (`EPDFilter`) | Reduces the full EPD database to a relevant subset before sending to the LLM, avoiding token limits |
| 4 — Semantic matching (LLM) | `matching/azure_matcher.py` + `matching/prompt_builder.py` | Sends a structured prompt to Azure OpenAI; returns JSON with `id`, `confidence`, `begruendung` per match |
| 5 — Confidence validation | `matching/epd_filter.py` (`ConfidenceValidator`) | Post-processes LLM output: caps confidence for exclusion terms, mismatched material types, and wrong layer names |

## Module responsibilities

- **`config/settings.py`** — single source of truth for all config. Imports `dotenv`, exposes typed class attributes (`AzureConfig`, `APIConfig`, `MatchingConfig`, etc.). Prints a config summary on every import — intentional.
- **`api/auth.py`** (`TokenManager`) — JWT token cache with auto-refresh for the EPD REST API.
- **`api/epd_client.py`** (`EPDAPIClient`) — fetches the full EPD list and parallel-loads detail records. All EPDs are loaded once and cached on `AzureEPDMatcher._epd_cache`.
- **`matching/azure_matcher.py`** (`AzureEPDMatcher`) — orchestrates the pipeline. Supports batch mode (all layers in one LLM call) and individual mode (one call per layer).
- **`matching/prompt_builder.py`** (`PromptBuilder`) — constructs the LLM prompt. Compact mode lists `id | name`; detail mode adds `technischeBeschreibung`, `anmerkungen`, etc. (controlled by `EPD_USE_DETAIL_MATCHING`).
- **`utils/asphalt_glossar.py`** — domain glossary for German road construction materials (TL Asphalt-StB standard). Contains `parse_material_input()` and `filter_epds_for_material()`.
- **`utils/cost_tracker.py`** — accumulates token counts and USD costs per session; printed at the end of each run.

## Input / output format

Input JSON (`input/input.json`):
```json
{
  "Gruppen": [
    { "NAME": "Asphaltdeckschicht", "MATERIAL": "AC 16 D S", "Volumen": 120.5, "GUID": ["..."] }
  ]
}
```

Output adds `id` (list of matched EPD IDs) and `id_confidence` (map of id → 0–100) to each Gruppe entry.

## Key design decisions

- **Batch vs. individual mode**: Batch (`EPD_USE_BATCH_MODE=true`) sends all layers in one LLM request — faster and cheaper but requires the model to produce structured output for N layers simultaneously. Individual mode is the fallback.
- **EPD pre-filtering is the main cost lever**: With 10 000+ EPDs in the database, the glossar filter (`EPDFilter`) is what makes LLM calls feasible. The filter returns all relevant matches, primary (correct layer) first; `PROMPT_MAX_EPD` is only a token-limit safety cap on the prompt, not a relevance filter.
- **Confidence validation (Stage 5) is rule-based**, not LLM-based: it caps scores for known mismatches (e.g. Bitumenbahnen matched to Asphalt) using `MATERIAL_MISMATCHES` and `AUSSCHLUSS_BEGRIFFE` lists in `epd_filter.py`.
- **The LLM response is always parsed defensively**: both `_parse_response` and `_parse_batch_response` strip markdown fences and fall back to regex extraction before giving up.

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical label names are used (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
