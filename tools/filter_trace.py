#!/usr/bin/env python
"""Filter-Trace: macht die Stage-3-Vorfilterung (EPDFilter) nachvollziehbar.

Für jedes Szenario (Material + Schichtname) wird die *echte* EPDFilter-Logik
ausgeführt und protokolliert:
  - welche und wie viele EPDs VOR dem Filter da waren,
  - welche und wie viele NACH dem Filter übrig sind,
  - in welcher Reihenfolge (primär zuerst, dann sekundär),
  - und – pro EPD – aus welchem Grund sie behalten / verworfen wurde.

Kept/Dropped stammen direkt aus EPDFilter.filter_for_materials (Ground Truth);
der Grund wird zusätzlich aus bewerte_kandidat bzw. dem gewählten Filter-Zweig
abgeleitet. Der Report kann dadurch nie von der echten Filterung abweichen.

Ausgabe je Szenario unter  <out>/<lauf>/<szenario>/ :
  00_input.csv          alle EPDs vor dem Filter (id, name, klassifizierung)
  01_kept_ordered.csv   verbliebene EPDs in finaler Reihenfolge (+ bucket + grund)
  02_dropped.csv        verworfene EPDs (+ grund)
  summary.md            Parsing-Ergebnis, gewählter Zweig, Zählungen, Vorschau
sowie <out>/<lauf>/index.md über alle Szenarien.

Aufruf (vom Repo-Root):
  python -m tools.filter_trace                # Fixtures (Default, deterministisch)
  python -m tools.filter_trace --source db    # echte lokale DB (data/oekobaudat.db)
  python -m tools.filter_trace --out reports  # anderes Ausgabe-Verzeichnis
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.asphalt_glossar import (
    AUSSCHLUSS_BEGRIFFE,
    MATERIAL_KATEGORIEN,
    _detect_material_category,
    parse_material_input,
)
from matching.matching_rules import bewerte_kandidat
from matching.epd_filter import EPDFilter

# Stopwörter analog Fall 3 in epd_filter._filter_epds
STOP_WORDS = {"mit", "und", "für", "der", "die", "das", "von", "nach", "gemäß"}


# =============================================================================
# FIXTURES — kleine, kuratierte EPD-Liste, die jeden Filter-Zweig auslöst
# =============================================================================

FIXTURE_EPDS: List[Dict[str, Any]] = [
    {"id": "fix-01", "name": "Asphaltdeckschicht AC 11 D S",
     "klassifizierung": "Mineralische Baustoffe / Asphalt / Deckschichten"},
    {"id": "fix-02", "name": "Splittmastixasphalt SMA 8 S Deckschicht",
     "klassifizierung": "Asphalt / Deckschichten"},
    {"id": "fix-03", "name": "Asphaltbinder AC 16 B S",
     "klassifizierung": "Asphalt / Binderschichten"},
    {"id": "fix-04", "name": "Asphalttragschicht AC 32 T S",
     "klassifizierung": "Asphalt / Tragschichten"},
    {"id": "fix-05", "name": "Gussasphalt MA 11",
     "klassifizierung": "Asphalt / Gussasphalt"},
    {"id": "fix-06", "name": "Bitumenbahn G 200 S4",
     "klassifizierung": "Abdichtung / Bitumenbahnen"},
    {"id": "fix-07", "name": "Schotter 0/45 Mineralgemisch",
     "klassifizierung": "Gesteinskörnung / Schotter"},
    {"id": "fix-08", "name": "Edelsplitt 2/5",
     "klassifizierung": "Gesteinskörnung / Splitt"},
    {"id": "fix-09", "name": "Frostschutzschicht Kiessand 0/32",
     "klassifizierung": "Ungebundene Gemische / Frostschutz"},
    {"id": "fix-10", "name": "Kiessand 0/32 Frostschutz",
     "klassifizierung": "Ungebundene Gemische / Frostschutzschicht"},
    {"id": "fix-11", "name": "Gesteinskörnungsgemisch 0/45",
     "klassifizierung": "Ungebundene Gemische / Mineralgemisch"},
    {"id": "fix-12", "name": "Bitumenbahn G 200 S4",
     "klassifizierung": "Abdichtung / Bitumenbahnen"},
    {"id": "fix-13", "name": "Schweißbahn Dachabdichtung",
     "klassifizierung": "Abdichtung / Bitumenbahnen"},
    {"id": "fix-14", "name": "Zementmörtel",
     "klassifizierung": "Mörtel / Zementmörtel"},
    {"id": "fix-15", "name": "Beton C25/30 Fahrbahndecke",
     "klassifizierung": "Beton / Straßenbeton"},
]

# (slug, material_name, schicht_name) — jeweils ein einzelnes Material pro Report
SCENARIOS: List[Tuple[str, str, str]] = [
    ("01_ac16ds_deckschicht", "AC 16 D S", "Asphaltdeckschicht"),
    ("02_sma_deckschicht", "SMA 8 S", "Deckschicht"),
    ("03_ac32ts_tragschicht", "AC 32 T S", "Tragschicht"),
    ("04_schotter_tragschicht", "Schotter 0/45", "Schottertragschicht"),
    ("05_frostschutz", "Gesteinskörnungsgemisch 0/32", "Frostschutzschicht"),
    ("06_abdichtung_bruecke", "Bitumenbahn", "Brückenabdichtung"),
]


# =============================================================================
# ZWEIG-ERKENNUNG + GRUND-ABLEITUNG (Spiegelung von epd_filter._filter_epds)
# =============================================================================

def detect_branch(parsed: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Ermittelt, welchen Filter-Zweig _filter_epds nehmen würde."""
    if parsed.get("ist_asphalt"):
        return "asphalt", None
    cat = _detect_material_category(
        parsed.get("material_original", ""),
        parsed.get("schicht_name_original") or "",
    )
    if cat and cat in MATERIAL_KATEGORIEN:
        return "kategorie", cat
    return "unbekannt", None


def _first_hit(text: str, terms: List[str]) -> Optional[str]:
    """Erster Begriff aus terms, der als Substring in text (lower) vorkommt."""
    for t in terms:
        if t.lower() in text:
            return t
    return None


def _material_words(parsed: Dict[str, Any]) -> List[str]:
    """Keyword-Liste analog Fall 3 in _filter_epds."""
    mat = parsed.get("material_original", "")
    sch = parsed.get("schicht_name_original") or ""
    return [
        w.lower() for w in f"{mat} {sch}".split()
        if len(w) > 2 and w.lower() not in STOP_WORDS
    ]


def explain(
    parsed: Dict[str, Any],
    branch: str,
    cat: Optional[str],
    epd: Dict[str, Any],
    kept: bool,
    is_primaer: bool,
) -> str:
    """Lesbarer Grund, warum eine EPD behalten / verworfen wurde."""
    combined = f"{epd.get('name', '')} {epd.get('klassifizierung', '')}".lower()

    # -------------------------------------------------- Fall 1: Asphalt
    if branch == "asphalt":
        b = bewerte_kandidat(parsed, epd)
        if not kept:
            if b.ausgeschlossen:
                return f"verworfen: Ausschluss-Begriff '{b.ausgeschlossen}'"
            if not b.ist_asphalt:
                return "verworfen: kein Asphalt-Bezug"
            return "verworfen: (unerwartet)"
        schicht_muss = parsed.get("schicht_epd_muss_enthalten") or "?"
        if is_primaer:
            txt = f"primär: Asphalt-Bezug + Schicht '{schicht_muss}' im EPD"
        else:
            txt = "sekundär: Asphalt-Bezug, aber Schicht passt nicht"
        if b.kategorie_konflikt:
            txt += (f"  [!] Kategorie-Konflikt '{b.kategorie_konflikt}' "
                    f"— Stage 3 lässt durch, Stage 5 würde Confidence cappen")
        return txt

    # -------------------------------------------------- Fall 2: Kategorie
    if branch == "kategorie":
        cat_info = MATERIAL_KATEGORIEN[cat]
        if not kept:
            g = _first_hit(combined, AUSSCHLUSS_BEGRIFFE)
            if g:
                return f"verworfen: globaler Ausschluss '{g}'"
            g = _first_hit(combined, cat_info["ausschluss"])
            if g:
                return f"verworfen: Kategorie-Ausschluss '{g}'"
            return f"verworfen: kein {cat}-Suchbegriff"
        if is_primaer:
            g = _first_hit(combined, cat_info["suchbegriffe"])
            return f"primär: {cat}-Suchbegriff '{g}'"
        return "sekundär: Fallback-Treffer über Material-Wort im EPD-Namen"

    # -------------------------------------------------- Fall 3: Unbekannt
    if not kept:
        g = _first_hit(combined, AUSSCHLUSS_BEGRIFFE)
        if g:
            return f"verworfen: globaler Ausschluss '{g}'"
        return "verworfen: kein Keyword-Treffer"
    g = _first_hit(combined, _material_words(parsed))
    return f"primär: Keyword '{g}'"


# =============================================================================
# AUSGABE-HELFER
# =============================================================================

BRANCH_LABEL = {
    "asphalt": "Fall 1 — Asphalt (typ-/schichtbasiert)",
    "kategorie": "Fall 2 — Nicht-Asphalt-Kategorie",
    "unbekannt": "Fall 3 — Unbekannt (Keyword-Suche)",
}


def _write_csv(path: Path, header: List[str], rows: List[List[Any]]) -> None:
    """Schreibt CSV mit UTF-8-BOM (Excel-freundlich, korrekte Umlaute)."""
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


def _md_table(header: List[str], rows: List[List[Any]]) -> str:
    """Erzeugt eine GitHub-Markdown-Tabelle."""
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        cells = [str(c).replace("|", "\\|") for c in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def run_scenario(
    epds: List[Dict[str, Any]],
    slug: str,
    material_name: str,
    schicht: str,
    out_root: Path,
) -> Dict[str, Any]:
    """Führt ein Szenario aus, schreibt die Dateien und liefert Kennzahlen."""
    parsed = parse_material_input(material_name, schicht)
    branch, cat = detect_branch(parsed)

    # Ground Truth aus der echten Filter-Logik
    flt = EPDFilter()
    result = flt.filter_for_materials(
        epds, [{"material_name": material_name, "context": {"NAME": schicht}}]
    )
    pm = result["per_material"][0]
    primaer_ids = {e.get("id") for e in pm["primaer"]}
    kept_ordered = result["combined_epds"]            # primär zuerst, dann sekundär
    kept_ids = {e.get("id") for e in kept_ordered}
    dropped = [e for e in epds if e.get("id") not in kept_ids]

    scen_dir = out_root / slug
    scen_dir.mkdir(parents=True, exist_ok=True)

    # 00 — alle EPDs vor dem Filter
    _write_csv(
        scen_dir / "00_input.csv",
        ["rang", "id", "name", "klassifizierung"],
        [[i + 1, e.get("id"), e.get("name"), e.get("klassifizierung")]
         for i, e in enumerate(epds)],
    )

    # 01 — behaltene EPDs in finaler Reihenfolge
    kept_rows = []
    for rang, e in enumerate(kept_ordered, 1):
        is_p = e.get("id") in primaer_ids
        kept_rows.append([
            rang,
            "primär" if is_p else "sekundär",
            e.get("id"), e.get("name"), e.get("klassifizierung"),
            explain(parsed, branch, cat, e, True, is_p),
        ])
    _write_csv(
        scen_dir / "01_kept_ordered.csv",
        ["rang", "bucket", "id", "name", "klassifizierung", "grund"],
        kept_rows,
    )

    # 02 — verworfene EPDs
    _write_csv(
        scen_dir / "02_dropped.csv",
        ["id", "name", "klassifizierung", "grund"],
        [[e.get("id"), e.get("name"), e.get("klassifizierung"),
          explain(parsed, branch, cat, e, False, False)] for e in dropped],
    )

    # summary.md
    before, after = len(epds), len(kept_ordered)
    n_prim = len(primaer_ids)
    n_sek = after - n_prim
    reduction = round((1 - after / before) * 100, 1) if before else 0.0

    preview = _md_table(
        ["rang", "bucket", "name", "grund"],
        [[r[0], r[1], r[3], r[5]] for r in kept_rows[:15]],
    ) if kept_rows else "_(keine Treffer)_"

    parsed_fields = {
        "ist_asphalt": parsed.get("ist_asphalt"),
        "typ": parsed.get("typ"),
        "schicht": parsed.get("schicht"),
        "schicht_epd_muss_enthalten": parsed.get("schicht_epd_muss_enthalten"),
        "quelle": parsed.get("quelle"),
        "erkannte_kategorie": cat,
    }
    parsed_md = _md_table(
        ["Feld", "Wert"],
        [[k, "" if v is None else v] for k, v in parsed_fields.items()],
    )

    summary = f"""# Filter-Trace: {material_name}  ·  Schicht „{schicht}"

**Gewählter Zweig:** {BRANCH_LABEL[branch]}{f" — Kategorie `{cat}`" if cat else ""}

## Zählungen
| | Anzahl |
|---|---|
| EPDs vor Filter | {before} |
| EPDs nach Filter | **{after}** |
| davon primär | {n_prim} |
| davon sekundär | {n_sek} |
| verworfen | {before - after} |
| Reduktion | {reduction} % |

## Parsing-Ergebnis (Stage 2)
{parsed_md}

## Reihenfolge nach dem Filter (Top 15)
Primär zuerst, dann sekundär — exakt die Reihenfolge, in der die EPDs an den LLM gehen.

{preview}

## Dateien
- `00_input.csv` — alle {before} EPDs vor dem Filter
- `01_kept_ordered.csv` — {after} behaltene EPDs in finaler Reihenfolge (+ Grund)
- `02_dropped.csv` — {before - after} verworfene EPDs (+ Grund)
"""
    (scen_dir / "summary.md").write_text(summary, encoding="utf-8")

    return {
        "slug": slug, "material": material_name, "schicht": schicht,
        "branch": BRANCH_LABEL[branch], "before": before, "after": after,
        "primaer": n_prim, "sekundaer": n_sek, "reduction": reduction,
    }


def write_index(out_root: Path, source: str, stats: List[Dict[str, Any]]) -> None:
    """Schreibt eine Übersicht über alle Szenarien."""
    table = _md_table(
        ["Szenario", "Material", "Schicht", "Zweig", "vorher", "nachher",
         "primär", "sekundär", "Reduktion %"],
        [[s["slug"], s["material"], s["schicht"], s["branch"],
          s["before"], s["after"], s["primaer"], s["sekundaer"], s["reduction"]]
         for s in stats],
    )
    content = f"""# Filter-Trace — Übersicht

**Datenquelle:** `{source}`  ·  **Lauf:** `{out_root.name}`

{table}

Jeder Szenario-Ordner enthält `summary.md` sowie die CSV-Dateien
`00_input.csv`, `01_kept_ordered.csv`, `02_dropped.csv`.
"""
    (out_root / "index.md").write_text(content, encoding="utf-8")


# =============================================================================
# DATEN LADEN
# =============================================================================

def load_epds(source: str) -> List[Dict[str, Any]]:
    """Lädt EPDs entweder aus den Fixtures oder der konfigurierten Datenquelle."""
    if source == "fixtures":
        return list(FIXTURE_EPDS)
    if source == "db":
        from datasources.factory import create_data_source
        return create_data_source().list_epds()
    raise ValueError(f"Unbekannte Quelle: {source!r} (erlaubt: fixtures, db)")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="Stage-3-Filter nachvollziehbar tracen.")
    ap.add_argument("--source", choices=["fixtures", "db"], default="fixtures",
                    help="Datenbasis: fixtures (Default) oder db (echte lokale DB)")
    ap.add_argument("--out", default="filter_reports",
                    help="Ausgabe-Wurzelverzeichnis (Default: filter_reports)")
    args = ap.parse_args()

    epds = load_epds(args.source)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = Path(args.out) / f"{args.source}_{stamp}"
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 70}\nFILTER-TRACE  ·  Quelle={args.source}  ·  {len(epds)} EPDs\n{'=' * 70}")

    stats = []
    for slug, material, schicht in SCENARIOS:
        s = run_scenario(epds, slug, material, schicht, out_root)
        stats.append(s)
        print(f"  {slug:28s} {material:24s} {s['before']:>6} -> {s['after']:>4} "
              f"(primär {s['primaer']}, sekundär {s['sekundaer']}, -{s['reduction']}%)")

    write_index(out_root, args.source, stats)
    print(f"\nReports geschrieben nach: {out_root}\n")


if __name__ == "__main__":
    main()
