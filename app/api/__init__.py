from .routes_tenders import router as tenders_router
from .routes_ingest import router as ingest_router
from .routes_health import router as health_router

__all__ = ["tenders_router", "ingest_router", "health_router"]
