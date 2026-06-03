"""Geteilte Matching-Regeln für Stage 3 (EPD-Vorfilterung) und Stage 5 (Confidence-Validierung).

Einzige Quelle für Ausschluss-, Kategorie- und Mismatch-Wissen.
Stage 3 (EPDFilter) und Stage 5 (ConfidenceValidator) sind dünne Aufrufer,
die Bewertung je nach Policy interpretieren.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from utils.asphalt_glossar import (
    AUSSCHLUSS_BEGRIFFE,
    ASPHALT_TYPES,
    _ist_ausgeschlossen,
    _ist_generisch_asphalt,
)

# Tiefbau-Scope: Whitelist der Ökobaudat-Klassifikationspfade, die für Straßenbau-EPD-
# Matching als domänenrelevant gelten. EPDs außerhalb dieser Präfixe (z.B. Sanitär,
# Bodenbeläge, Stahlbleche) werden vor der Drei-Fall-Filterlogik strukturell ausgeschlossen.
# Empirisch in DB-Snapshot validiert (siehe docs/studie/paper_design.md §1.2.2).
TIEFBAU_KLASSIFIKATION_PREFIXES: List[str] = [
    "Mineralische Baustoffe / Asphalt",
    "Mineralische Baustoffe / Zuschläge",
    "Mineralische Baustoffe / Mörtel und Beton / Beton",
]


def ist_tiefbau_relevant(epd: Dict[str, Any]) -> bool:
    """True, wenn der Klassifizierungspfad des EPDs unter einem Tiefbau-Präfix liegt."""
    klass = epd.get("klassifizierung", "")
    return any(klass.startswith(p) for p in TIEFBAU_KLASSIFIKATION_PREFIXES)


# Mismatch-Wissen: diese EPD-Begriffe passen NICHT zum jeweiligen Material-Typ.
# War früher dupliziert in epd_filter.MATERIAL_MISMATCHES.
MATERIAL_MISMATCHES: Dict[str, List[str]] = {
    "asphalt": [
        "bitumenbahn", "bitumenbahnen", "dachbahn", "dachabdichtung",
        "schweißbahn", "kaltselbstklebebahn", "dampfsperre",
        "emulsion",
    ],
    "schotter": [
        "bitumenbahn", "bitumenbahnen", "asphalt", "gussasphalt",
        "emulsion", "dampfsperre",
    ],
}


@dataclass
class Bewertung:
    """Fakten über ein (Material, EPD)-Paar. Keine Policy."""
    ist_asphalt: bool                  # EPD hat Asphalt-Bezug
    ausgeschlossen: Optional[str]      # erster treffender Ausschluss-Begriff, oder None
    schicht_passt: bool                # schicht_epd_muss_enthalten trifft auf EPD
    kategorie_konflikt: Optional[str]  # erster treffender Mismatch-Begriff, oder None


def get_material_type(parsed_material: Dict[str, Any]) -> Optional[str]:
    """Ermittelt den groben Material-Typ für die Mismatch-Prüfung."""
    material_orig = parsed_material.get("material_original", "").lower()
    schicht_orig = (parsed_material.get("schicht_name_original") or "").lower()
    combined = f"{material_orig} {schicht_orig}"
    if parsed_material.get("ist_asphalt"):
        return "asphalt"
    if any(kw in combined for kw in ["schotter", "kies", "splitt", "frostschutz"]):
        return "schotter"
    return None


def bewerte_kandidat(material: Dict[str, Any], epd: Dict[str, Any]) -> Bewertung:
    """
    Gibt die geteilten Fakten über ein (Material, EPD)-Paar zurück.

    Args:
        material: Parsed-Material-Dict (Output von parse_material_input).
        epd:      EPD-Dict mit mindestens 'name' und 'klassifizierung'.

    Returns:
        Bewertung mit vier Fakten. Stage 3 und Stage 5 interpretieren sie je nach Policy.
    """
    epd_name = epd.get("name", "").lower()
    epd_klassifizierung = epd.get("klassifizierung", "").lower()
    combined = f"{epd_name} {epd_klassifizierung}"

    # 1. Ausschluss-Begriff (Exklusion: gegen combined)
    ausgeschlossen: Optional[str] = None
    for term in AUSSCHLUSS_BEGRIFFE:
        if term.lower() in combined:
            ausgeschlossen = term
            break

    # 2. Asphalt-Bezug der EPD (gegen combined: Klassifizierung "Asphalt/..." ist zuverlässig,
    #    kein Explosionsrisiko wie bei generischen Kategorie-Suchbegriffen).
    #    Generische Begriffe ('asphalt', 'bitumen' …) werden ausschließlich von
    #    _ist_generisch_asphalt mit Negativ-Kontext-Logik behandelt; aus typ_begriffe
    #    werden sie ausgefiltert, damit Bodenbelag-EPDs mit Bitumen-Trägerplatte hier
    #    nicht naiv als Asphalt durchrutschen (v2 Precision-Fix).
    typ_begriffe: List[str] = []
    if material.get("typ") and material["typ"] in ASPHALT_TYPES:
        _generic = {"asphalt", "bitumen", "bituminös", "bituminos", "aspahlt"}
        typ_begriffe = [
            b.lower() for b in ASPHALT_TYPES[material["typ"]]["suchbegriffe"]
            if b.lower() not in _generic
        ]
    ist_asphalt = _ist_generisch_asphalt(combined) or any(t in combined for t in typ_begriffe)

    # 3. Schicht-Treffer (Inklusion: gegen name — verhindert False Positives über Klassifizierung)
    schicht_muss = (material.get("schicht_epd_muss_enthalten") or "").lower()
    schicht_passt = bool(schicht_muss and schicht_muss in epd_name)

    # 4. Kategorie-/Typ-Konflikt (Exklusion: gegen combined)
    material_type = get_material_type(material)
    kategorie_konflikt: Optional[str] = None
    if material_type:
        for term in MATERIAL_MISMATCHES.get(material_type, []):
            if term in combined:
                kategorie_konflikt = term
                break

    return Bewertung(
        ist_asphalt=ist_asphalt,
        ausgeschlossen=ausgeschlossen,
        schicht_passt=schicht_passt,
        kategorie_konflikt=kategorie_konflikt,
    )


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    from utils.asphalt_glossar import parse_material_input

    print("=" * 70)
    print("MATCHING-RULES TEST")
    print("=" * 70)

    # (mat_name, schicht, epd_name, epd_klass,
    #  erw_ausgeschlossen, erw_ist_asphalt, erw_schicht_passt, erw_kategorie_konflikt, beschreibung)
    tests = [
        (
            "AC 16 D S", "Deckschicht",
            "Asphaltdeckschicht AC 11 D S",
            "Mineralische Baustoffe / Asphalt / Deckschichten",
            None, True, True, None,
            "Deckschicht-Match — alle Fakten positiv",
        ),
        (
            "AC 16 B S", "Binderschicht",
            "Asphalttragschicht AC 32 T S",
            "Mineralische Baustoffe / Asphalt / Tragschichten",
            None, True, False, None,
            "Falscher Schicht-Typ: schicht_passt=False, kein Konflikt",
        ),
        (
            "AC 16 D S", "Deckschicht",
            "Bitumenbahn G 200 S4",
            "Abdichtung / Bitumenbahnen",
            None, False, False, "bitumenbahn",
            "Bitumenbahn: Negativ-Kontext greift -> ist_asphalt=False (Bitumenbahn ist kein Asphaltmischgut); Kategorie-Konflikt fängt sie als Abdichtungs-Produkt ab",
        ),
        (
            "AC 16 T S", "Bituminöse Tragschicht",
            "Betonpflaster C25/30",
            "Mineralische Baustoffe / Pflastersteine",
            None, False, False, None,
            "Betonpflaster: kein globaler Ausschluss (Tiefbau-valide), kein Asphalt-Bezug im Namen -> raus",
        ),
        (
            "Asphalttragschicht", "Tragschicht",
            "Asphalttragschicht AC 32 T N",
            "Asphalt / Tragschichten",
            None, True, True, None,
            "Fuzzy-Match Tragschicht: alle Fakten positiv",
        ),
        (
            "Schotter 0/45", "Nicht bituminöse Tragschicht",
            "Asphaltbeton AC 16",
            "Mineralische Baustoffe / Asphalt / Tragschichten",
            None, True, False, "asphalt",
            "Schotter vs. Asphalt-EPD: Kategorie-Konflikt; schicht_passt=False (Inklusion gegen name, 'trag' nur in Klassifizierung)",
        ),
        (
            "AC 16 B S", "Binderschicht",
            "Genadelte Teppichfliesen mit einer Faserzusammensetzung aus 80% PP, 20% PET und einer Bitumenschwerbeschichtung",
            "Kunststoffe / Bodenbeläge / Textile Bodenbeläge",
            None, False, False, None,
            "Teppichfliese mit Bitumenschwerbeschichtung: 'bitumen' im Namen, aber Negativ-Kontext greift → ist_asphalt=False (Fix für v2-Precision-Bug)",
        ),
    ]

    passed = 0
    for (mat, schicht, epd_name, epd_klass,
         erw_ausg, erw_asph, erw_schicht, erw_konfl, desc) in tests:

        parsed = parse_material_input(mat, schicht)
        epd = {"name": epd_name, "klassifizierung": epd_klass}
        b = bewerte_kandidat(parsed, epd)

        ok = (
            b.ausgeschlossen == erw_ausg
            and b.ist_asphalt == erw_asph
            and b.schicht_passt == erw_schicht
            and b.kategorie_konflikt == erw_konfl
        )
        status = "[OK]  " if ok else "[FAIL]"
        print(f"\n{status} {desc}")
        if not ok:
            print(f"  Material:  {mat!r} / {schicht!r}")
            print(f"  EPD:       {epd_name!r}")
            print(f"  Erwartet:  ausgeschlossen={erw_ausg!r}, ist_asphalt={erw_asph}, "
                  f"schicht_passt={erw_schicht}, kategorie_konflikt={erw_konfl!r}")
            print(f"  Erhalten:  ausgeschlossen={b.ausgeschlossen!r}, ist_asphalt={b.ist_asphalt}, "
                  f"schicht_passt={b.schicht_passt}, kategorie_konflikt={b.kategorie_konflikt!r}")
        else:
            passed += 1

    print(f"\n{'=' * 70}")
    print(f"Bewertung-Tests: {passed}/{len(tests)} bestanden")

    # =========================================================================
    # ist_tiefbau_relevant — Helper-Tests
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("TIEFBAU-WHITELIST TEST")
    print(f"{'=' * 70}")

    tiefbau_tests = [
        ({"klassifizierung": "Mineralische Baustoffe / Asphalt / Tragschichten"}, True,
         "Asphalt-Tragschicht"),
        ({"klassifizierung": "Mineralische Baustoffe / Zuschläge / Naturstein"}, True,
         "Zuschlag-Naturstein"),
        ({"klassifizierung": "Mineralische Baustoffe / Mörtel und Beton / Beton"}, True,
         "Straßenbeton (Whitelist-Reservescope)"),
        ({"klassifizierung": "Kunststoffe / Bodenbeläge / Textile Bodenbeläge"}, False,
         "Teppichfliese — strukturell außerhalb Tiefbau"),
        ({"klassifizierung": "Metalle / Stahl und Eisen / Stahlbleche"}, False,
         "Stahlblech — strukturell außerhalb Tiefbau"),
        ({"klassifizierung": "Gebäudetechnik / Sanitär / Armaturen"}, False,
         "Brauseset — strukturell außerhalb Tiefbau"),
        ({"klassifizierung": "Dämmstoffe / Schaumglas / Granulat"}, False,
         "Schaumglasschotter — Dämmstoff, RStO-unüblich"),
        ({"klassifizierung": "Mineralische Baustoffe / Steine und Elemente / Betonfertigteile und Betonwaren"}, False,
         "Betonpflasterstein — bewusst NICHT in Whitelist für v2"),
        ({"klassifizierung": "Mineralische Baustoffe / Bindemittel / Zement"}, False,
         "Zement — Bindemittel, keine Schicht"),
    ]
    tb_passed = 0
    for epd, expected, desc in tiefbau_tests:
        got = ist_tiefbau_relevant(epd)
        ok = got == expected
        status = "[OK]  " if ok else "[FAIL]"
        print(f"{status} {desc} -> {got} (erwartet {expected})")
        if ok:
            tb_passed += 1
    print(f"\nTiefbau-Tests: {tb_passed}/{len(tiefbau_tests)} bestanden")

    total = passed + tb_passed
    total_n = len(tests) + len(tiefbau_tests)
    print(f"\nGESAMT: {total}/{total_n} bestanden")
    if total < total_n:
        raise SystemExit(1)
