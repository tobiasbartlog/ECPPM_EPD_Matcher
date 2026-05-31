"""Mapping von soda4LCA-JSON auf den EPD-Vertrag.

Einzige Stelle mit API-Feldnamen. Rein-funktional, kein I/O.
"""
from typing import Any, Dict


def _extract_lang(value: Any, lang: str = "de") -> str:
    """Extrahiert Text für eine Sprache aus mehrsprachigem Feld.

    Fallback-Reihenfolge: bevorzugte Sprache → 'en' → erster Eintrag → ''.
    Unterstützt String, Liste von {lang/value} oder {@xml:lang/#text}.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        fallback_en = ""
        fallback_any = ""
        for item in value:
            if not isinstance(item, dict):
                continue
            item_lang = item.get("lang") or item.get("@xml:lang", "")
            text = str(item.get("value") or item.get("#text") or "")
            if item_lang == lang:
                return text
            if item_lang == "en" and not fallback_en:
                fallback_en = text
            if not fallback_any:
                fallback_any = text
        return fallback_en or fallback_any
    if isinstance(value, dict):
        return str(value.get("value") or value.get("#text") or "")
    return ""


def _safe_get(obj: Any, *keys: str) -> Any:
    """Sicherer Pfad-Zugriff auf verschachtelte Dicts."""
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _classification_path(data: Dict[str, Any]) -> str:
    """Baut deutschen Klassifikationspfad aus ILCD-Struktur.

    Sucht in processInformation.dataSetInformation.classificationInformation
    sowie direkt im classific-Feld des Listen-Eintrags.
    """
    # Listen-Eintrag: classific ist meist schon ein Pfad-String
    if "classific" in data:
        return _extract_lang(data["classific"])

    # Detail-Eintrag: ILCD classification
    classifications = _safe_get(
        data,
        "processInformation",
        "dataSetInformation",
        "classificationInformation",
        "classification",
    )
    if not classifications:
        return ""
    if isinstance(classifications, dict):
        classifications = [classifications]
    if not isinstance(classifications, list):
        return ""

    for cl in classifications:
        if not isinstance(cl, dict):
            continue
        classes = cl.get("class") or []
        if isinstance(classes, dict):
            classes = [classes]
        if not isinstance(classes, list):
            continue
        sorted_classes = sorted(
            (c for c in classes if isinstance(c, dict)),
            key=lambda c: int(c.get("@level", 0) if c.get("@level") is not None else 0),
        )
        parts = [
            _extract_lang(c.get("value") or c.get("name") or "")
            for c in sorted_classes
        ]
        parts = [p for p in parts if p]
        if parts:
            return " / ".join(parts)

    return ""


def map_list_item(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mappt einen soda4LCA Listen-Eintrag auf den EPD-Vertrag."""
    return {
        "id": str(data.get("uuid") or ""),
        "name": _extract_lang(data.get("name")),
        "klassifizierung": _extract_lang(data.get("classific")),
        "referenzjahr": str(data.get("refYear") or ""),
        "gueltigkeit": str(data.get("validUntil") or ""),
        "gliederungsnummer": str(data.get("classificId") or ""),
        "bauDatRef": "",
    }


def map_detail(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mappt einen soda4LCA ILCD-Detail-Datensatz auf den EPD-Vertrag."""
    proc_info = data.get("processInformation") or {}
    dataset_info = (proc_info.get("dataSetInformation") or {})
    technology = (proc_info.get("technology") or {})
    modelling = data.get("modellingAndValidation") or {}
    data_sources = (
        (modelling.get("dataSourcesTreatmentAndRepresentativeness") or {})
    )

    return {
        "id": str(_safe_get(dataset_info, "UUID") or ""),
        "name": _extract_lang(
            _safe_get(dataset_info, "name", "baseName")
            or _safe_get(dataset_info, "name")
        ),
        "klassifizierung": _classification_path(data),
        "referenzjahr": "",
        "gueltigkeit": "",
        "gliederungsnummer": str(
            _safe_get(dataset_info, "classificationInformation", "classificId") or ""
        ),
        "bauDatRef": "",
        "technischeBeschreibung": _extract_lang(
            _safe_get(technology, "technologyDescriptionAndIncludedProcesses")
        ),
        "anwendungsgebiet": _extract_lang(
            _safe_get(technology, "technologicalApplicability")
        ),
        "anmerkungen": _extract_lang(
            _safe_get(dataset_info, "generalComment")
        ),
        "anwendungshinweis": _extract_lang(
            _safe_get(data_sources, "useAdviceForDataSet")
        ),
    }


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("OEKOBAUDAT MAPPING TEST")
    print("=" * 70)

    # (a) map_list_item: Klassifizierung enthält Asphalt/Trag
    list_item = {
        "uuid": "abc-123",
        "name": "Asphalttragschicht AC 32 T S",
        "classific": "Mineralische Baustoffe / Asphalt / Tragschichten",
        "refYear": "2021",
        "validUntil": "2026",
        "classificId": "6.2.1",
    }
    result = map_list_item(list_item)
    assert result["id"] == "abc-123", f"id falsch: {result['id']}"
    assert "Asphalt" in result["klassifizierung"], f"Keine Asphalt-Klassifizierung: {result['klassifizierung']}"
    assert "Trag" in result["klassifizierung"], f"Kein Trag: {result['klassifizierung']}"
    print(f"[OK] map_list_item: klassifizierung='{result['klassifizierung']}'")

    # (b) map_detail: Sprache [en,de] und [de,en] → immer Deutsch
    def _make_detail(lang_order):
        texts = {"de": "Technische Beschreibung auf Deutsch", "en": "Technical description in English"}
        return {
            "processInformation": {
                "dataSetInformation": {
                    "UUID": "uuid-456",
                    "name": {"baseName": [{"lang": l, "value": f"Name_{l}"} for l in lang_order]},
                    "generalComment": [{"lang": l, "value": texts[l]} for l in lang_order],
                },
                "technology": {
                    "technologyDescriptionAndIncludedProcesses": [
                        {"lang": l, "value": texts[l]} for l in lang_order
                    ],
                    "technologicalApplicability": [
                        {"lang": l, "value": f"Anwendung_{l}"} for l in lang_order
                    ],
                },
            },
            "modellingAndValidation": {
                "dataSourcesTreatmentAndRepresentativeness": {
                    "useAdviceForDataSet": [
                        {"lang": l, "value": f"Hinweis_{l}"} for l in lang_order
                    ],
                },
            },
        }

    for order in [["en", "de"], ["de", "en"]]:
        r = map_detail(_make_detail(order))
        assert r["technischeBeschreibung"] == "Technische Beschreibung auf Deutsch", \
            f"Sprache falsch ({order}): {r['technischeBeschreibung']}"
        assert r["anmerkungen"] == "Technische Beschreibung auf Deutsch", \
            f"anmerkungen falsch ({order})"
        print(f"[OK] map_detail Sprachreihenfolge {order}: '{r['technischeBeschreibung'][:40]}'")

    # (c) Fehlende Detailfelder → leer, kein Crash
    minimal = {
        "processInformation": {
            "dataSetInformation": {"UUID": "min-789"},
            "technology": {},
        },
    }
    r = map_detail(minimal)
    assert r["technischeBeschreibung"] == "", f"Sollte leer sein: {r['technischeBeschreibung']}"
    assert r["anwendungshinweis"] == "", f"Sollte leer sein: {r['anwendungshinweis']}"
    print("[OK] map_detail fehlende Felder: leer, kein Crash")

    print("\nAlle Mapping-Tests bestanden")
