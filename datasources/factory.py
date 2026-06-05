"""Factory für EPD-Datenquellen.

Wählt anhand EPD_DATA_SOURCE (online / oekobaudat / local / local-custom) die
Implementierung. local und local-custom teilen denselben LocalEPDStore-Code-Pfad und
unterscheiden sich nur in der DB-Datei (reine vs. custom-angereicherte Kopie).
TokenManager und EPDAPIClient werden nur im online-Pfad und lazy konstruiert.
"""
from config.settings import DataSourceConfig
from datasources.base import EPDDataSource


def create_data_source() -> EPDDataSource:
    """Gibt die konfigurierte EPD-Datenquelle zurück."""
    source = DataSourceConfig.SOURCE.lower().strip()

    if source == "oekobaudat":
        from datasources.oekobaudat_client import OekobaudatClient
        return OekobaudatClient()

    if source == "local":
        from datasources.local_store import LocalEPDStore
        return LocalEPDStore()

    if source == "local-custom":
        from datasources.local_store import LocalEPDStore
        return LocalEPDStore(db_path=DataSourceConfig.LOCAL_CUSTOM_DB_PATH)

    if source == "online":
        from api.auth import TokenManager
        from api.epd_client import EPDAPIClient
        return EPDAPIClient(TokenManager())

    raise ValueError(
        f"Unbekannte EPD_DATA_SOURCE: '{source}'. "
        "Erlaubte Werte: online, oekobaudat, local, local-custom"
    )
