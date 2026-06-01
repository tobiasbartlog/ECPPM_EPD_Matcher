"""
EPD-Vorfilterung für effizienteres Matching.

Stage 3: Pre-filtering  (EPDFilter)
Stage 5: Confidence Validation  (ConfidenceValidator)

Beide lesen ihre Fakten aus matching_rules.bewerte_kandidat —
die einzige Quelle für Ausschluss-, Kategorie- und Mismatch-Wissen.
"""

from typing import Dict, Any, List, Optional, Tuple

from config.settings import ValidationConfig, GlossarConfig, ContextConfig
from utils.asphalt_glossar import (
    parse_material_input,
    _detect_material_category,
    MATERIAL_KATEGORIEN,
    _ist_ausgeschlossen,
)
from matching.matching_rules import bewerte_kandidat, get_material_type


class EPDFilter:
    """Stage 3: Filtert EPDs basierend auf Material-Analyse."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def filter_for_materials(
            self,
            all_epds: List[Dict[str, Any]],
            materials: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Filtert EPDs für mehrere Materialien."""
        per_material = {}
        stats = {
            "total_epds": len(all_epds),
            "materials_count": len(materials),
            "filtered_per_material": []
        }

        for idx, mat in enumerate(materials):
            material_name = mat.get("material_name", "")
            schicht_name = mat.get("context", {}).get("NAME", "")

            parsed = parse_material_input(material_name, schicht_name)
            primaer, sekundaer = self._filter_epds(all_epds, parsed)

            combined = primaer + sekundaer
            per_material[idx] = {
                "parsed": parsed,
                "primaer": primaer,
                "sekundaer": sekundaer,
                "combined": combined
            }

            stats["filtered_per_material"].append({
                "material": material_name,
                "schicht": schicht_name,
                "primaer_count": len(primaer),
                "sekundaer_count": len(sekundaer),
                "total_filtered": len(combined)
            })

            if self.debug:
                print(f"  Material {idx + 1}: {material_name}")
                print(f"    Parsed: {parsed.get('typ', 'N/A')} / {parsed.get('schicht', 'N/A')}")
                print(f"    Primär: {len(primaer)}, Sekundär: {len(sekundaer)}")

        # Primär-zuerst über alle Materialien, dann sekundär — dedupliziert.
        # So bleibt eine relevanz-sortierte Reihenfolge erhalten, falls Stage 4
        # die Liste später auf MAX_EPD_IN_PROMPT kürzt (gute Treffer fallen nie raus).
        combined_epds: List[Dict[str, Any]] = []
        seen_ids = set()
        for bucket in ("primaer", "sekundaer"):
            for idx in sorted(per_material):
                for epd in per_material[idx][bucket]:
                    epd_id = epd.get("id")
                    if epd_id in seen_ids:
                        continue
                    seen_ids.add(epd_id)
                    combined_epds.append(epd)

        stats["combined_count"] = len(combined_epds)
        stats["reduction_percent"] = round(
            (1 - len(combined_epds) / len(all_epds)) * 100, 1
        ) if all_epds else 0

        if self.debug:
            print(f"\n  Gesamt: {len(all_epds)} → {len(combined_epds)} EPDs ({stats['reduction_percent']}% Reduktion)")

        return {
            "combined_epds": combined_epds,
            "per_material": per_material,
            "stats": stats
        }

    def filter_for_single_material(
            self,
            all_epds: List[Dict[str, Any]],
            material_name: str,
            schicht_name: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Filtert EPDs für ein einzelnes Material."""
        parsed = parse_material_input(material_name, schicht_name)
        primaer, sekundaer = self._filter_epds(all_epds, parsed)
        return primaer + sekundaer, parsed

    def _filter_epds(
            self,
            all_epds: List[Dict[str, Any]],
            parsed: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Drei-Fall-Filterlogik für ein geparstets Material."""

        # =====================================================================
        # FALL 1: Asphalt — bewerte_kandidat liefert die Fakten
        # =====================================================================
        if parsed.get("ist_asphalt"):
            primaer: List[Dict[str, Any]] = []
            sekundaer: List[Dict[str, Any]] = []
            for epd in all_epds:
                b = bewerte_kandidat(parsed, epd)
                if b.ausgeschlossen:
                    continue
                if b.kategorie_konflikt:
                    continue
                if not b.ist_asphalt:
                    continue
                if b.schicht_passt:
                    primaer.append(epd)
                else:
                    sekundaer.append(epd)
            return primaer, sekundaer

        # =====================================================================
        # FALL 2: Nicht-Asphalt — kategorie-basierte Filterung
        # Inklusion: Suchbegriffe gegen name (spezifisch).
        # Exklusion: globaler Ausschluss + Kategorie-Ausschluss gegen combined.
        # =====================================================================
        material_orig = parsed.get("material_original", "")
        schicht_orig = parsed.get("schicht_name_original", "") or ""
        category = _detect_material_category(material_orig, schicht_orig)

        if category and category in MATERIAL_KATEGORIEN:
            cat_info = MATERIAL_KATEGORIEN[category]
            suchbegriffe = [s.lower() for s in cat_info["suchbegriffe"]]
            ausschluss = [a.lower() for a in cat_info["ausschluss"]]
            primaer = []
            sekundaer = []
            for epd in all_epds:
                epd_name = epd.get("name", "").lower()
                epd_klassifizierung = epd.get("klassifizierung", "").lower()
                combined = f"{epd_name} {epd_klassifizierung}"
                if _ist_ausgeschlossen(combined):
                    continue
                if any(excl in combined for excl in ausschluss):
                    continue
                if any(such in epd_name for such in suchbegriffe):
                    primaer.append(epd)
            if len(primaer) < 10:
                material_words = [w for w in material_orig.lower().split() if len(w) > 3]
                for epd in all_epds:
                    if epd in primaer:
                        continue
                    epd_name = epd.get("name", "").lower()
                    if any(word in epd_name for word in material_words):
                        sekundaer.append(epd)
            return primaer, sekundaer

        # =====================================================================
        # FALL 3: Unbekannt — keyword-basierte Suche gegen name.
        # Exklusion weiter gegen combined.
        # =====================================================================
        stop_words = {"mit", "und", "für", "der", "die", "das", "von", "nach", "gemäß"}
        material_words = [
            w.lower() for w in f"{material_orig} {schicht_orig}".split()
            if len(w) > 2 and w.lower() not in stop_words
        ]
        if not material_words:
            return all_epds, []
        primaer = []
        for epd in all_epds:
            epd_name = epd.get("name", "").lower()
            epd_klassifizierung = epd.get("klassifizierung", "").lower()
            combined = f"{epd_name} {epd_klassifizierung}"
            if _ist_ausgeschlossen(combined):
                continue
            if any(word in epd_name for word in material_words):
                primaer.append(epd)
        return primaer, []

    @staticmethod
    def get_filter_summary(stats: Dict[str, Any]) -> str:
        """Generiert lesbare Zusammenfassung der Filterung."""
        lines = [
            f"EPD-Filterung: {stats['total_epds']} → {stats['combined_count']} EPDs",
            f"Reduktion: {stats['reduction_percent']}%",
            f"Materialien: {stats['materials_count']}",
            ""
        ]
        for i, mat_stat in enumerate(stats.get("filtered_per_material", []), 1):
            lines.append(
                f"  {i}. {mat_stat['material'][:40]}... → "
                f"{mat_stat['primaer_count']} primär, {mat_stat['sekundaer_count']} sekundär"
            )
        return "\n".join(lines)


# =============================================================================
# STAGE 5: CONFIDENCE-VALIDATOR
# =============================================================================

class ConfidenceValidator:
    """Stage 5: Validiert und korrigiert GPT-Confidence-Werte.

    Liest Fakten aus bewerte_kandidat; die Cap-Policy (Schwellwerte) bleibt hier.
    """

    @staticmethod
    def validate_match(
            epd: Dict[str, Any],
            parsed_material: Dict[str, Any],
            gpt_confidence: int
    ) -> Tuple[int, str]:
        """Validiert einen einzelnen Match und korrigiert Confidence wenn nötig."""
        max_excluded = ValidationConfig.MAX_CONFIDENCE_EXCLUDED
        b = bewerte_kandidat(parsed_material, epd)

        # 1. Ausschluss-Check
        if b.ausgeschlossen:
            return min(gpt_confidence, max_excluded), f"Ausschluss-Begriff '{b.ausgeschlossen}' gefunden"

        # 2. Kategorie-/Typ-Konflikt
        if b.kategorie_konflikt:
            material_type = get_material_type(parsed_material)
            return min(gpt_confidence, max_excluded), f"'{b.kategorie_konflikt}' passt nicht zu {material_type}"

        # 3. Schicht-Check (nur wenn PREFER_NAME_FIELD und Schicht bekannt)
        schicht_muss = parsed_material.get("schicht_epd_muss_enthalten", "")
        if schicht_muss and ContextConfig.PREFER_NAME_FIELD:
            if not b.schicht_passt:
                if b.ist_asphalt:
                    return min(gpt_confidence, 60), f"Schicht-Begriff '{schicht_muss}' fehlt"
                else:
                    return min(gpt_confidence, 35), f"Schicht-Begriff '{schicht_muss}' fehlt + falscher Typ"

        # 4. Asphalt-Typ-Check
        if parsed_material.get("ist_asphalt") and not b.ist_asphalt:
            return min(gpt_confidence, 35), "Kein Asphalt-Bezug im EPD"

        return gpt_confidence, "Validiert"

    @staticmethod
    def validate_batch_results(
            matches_per_schicht: List[List[Dict[str, Any]]],
            materials: List[Dict[str, Any]],
            epds: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Validiert alle Batch-Ergebnisse. Filtert Ergebnisse unter MIN_CONFIDENCE."""
        epd_by_id = {str(e.get("id")): e for e in epds}
        min_confidence = ValidationConfig.MIN_CONFIDENCE

        validated_results = []

        for schicht_idx, matches in enumerate(matches_per_schicht):
            material = materials[schicht_idx] if schicht_idx < len(materials) else {}
            material_name = material.get("material_name", "")
            schicht_name = material.get("context", {}).get("NAME", "")

            parsed = parse_material_input(material_name, schicht_name)

            validated_matches = []
            for match in matches:
                epd_id = str(match.get("uuid", ""))
                epd = epd_by_id.get(epd_id, {})
                gpt_confidence = match.get("confidence", 50)

                new_confidence, grund = ConfidenceValidator.validate_match(
                    epd, parsed, gpt_confidence
                )

                if new_confidence < min_confidence:
                    continue

                validated_match = match.copy()
                validated_match["confidence"] = new_confidence

                if new_confidence != gpt_confidence:
                    original_reason = match.get("begruendung", "")
                    validated_match["begruendung"] = f"{original_reason} [Korrigiert: {grund}]"
                    validated_match["confidence_original"] = gpt_confidence

                validated_matches.append(validated_match)

            validated_matches.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            validated_results.append(validated_matches)

        return validated_results


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EPD-FILTER TEST")
    print("=" * 70)
    print(f"ValidationConfig.MIN_CONFIDENCE: {ValidationConfig.MIN_CONFIDENCE}")
    print(f"ValidationConfig.MAX_CONFIDENCE_EXCLUDED: {ValidationConfig.MAX_CONFIDENCE_EXCLUDED}")

    test_cases = [
        ("Bitumenbahnen G 200 S4", "AC 16 D S", "Deckschicht", "<=20 (Kategorie-Konflikt)"),
        ("Asphalttragschicht", "AC 16 D S", "Deckschicht", "<=60 nur wenn PREFER_NAME_FIELD=true, sonst 85"),
        ("Asphaltdeckschicht", "AC 16 D S", "Deckschicht", "85 (korrekte Deckschicht)"),
    ]

    for epd_name, material, schicht, erwartung in test_cases:
        epd = {"name": epd_name, "klassifizierung": ""}
        parsed = parse_material_input(material, schicht)
        new_conf, grund = ConfidenceValidator.validate_match(epd, parsed, 85)
        print(f"\nEPD: {epd_name} -> {new_conf}% ({grund})")
        print(f"  Erwartung: {erwartung}")
