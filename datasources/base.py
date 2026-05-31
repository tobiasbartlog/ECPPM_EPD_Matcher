"""EPD-Datenquelle Protocol und Vertrag-Konstanten."""
from typing import Protocol, List, Dict, Any, Optional, runtime_checkable

# Single source of truth for EPD contract columns
EPD_LIST_FIELDS = (
    "id", "name", "klassifizierung",
    "referenzjahr", "gueltigkeit", "gliederungsnummer", "bauDatRef",
)
EPD_DETAIL_FIELDS = EPD_LIST_FIELDS + (
    "technischeBeschreibung", "anmerkungen",
    "anwendungsgebiet", "anwendungshinweis",
)


@runtime_checkable
class EPDDataSource(Protocol):
    """Gemeinsame Schnittstelle für alle EPD-Datenquellen."""

    def list_epds(
        self,
        labels: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]: ...

    def get_epd_details(
        self,
        epd_ids: List[str],
        max_workers: int = 10,
    ) -> List[Dict[str, Any]]: ...

    def count_epds(self) -> int: ...
