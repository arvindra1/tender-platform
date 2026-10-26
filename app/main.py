import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.db.connection import init_db, get_sync_db
from app.db.migrations import run_migrations
from app.api import tenders_router, ingest_router, health_router
from app.services.ingestion_service import IngestionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("indic_tender.main")

static_dir = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("==================================================")
    logger.info("Initializing Indic Tender Platform...")
    logger.info("Target Source 1: Central Public Procurement Portal (CPPP)")
    logger.info("Safe Public Access Policy: ENFORCED")
    logger.info("==================================================")

    # 1. Initialize MongoDB connection (or in-memory mock fallback)
    db = init_db()

    # 2. Run Database Migrations and ensure indexes
    applied = run_migrations(db)
    logger.info(f"Database migrations evaluated. Applied: {len(applied)}")

    # 3. Seed initial baseline if database is completely empty
    tenders_count = db["tenders"].count_documents({})
    if tenders_count == 0:
        logger.info("Database is empty on initial startup. Running initial baseline ingestion (FIXTURE_SNAPSHOT)...")
        service = IngestionService(db=db)
        service.run_cppp_ingestion(mode="FIXTURE_SNAPSHOT")
        logger.info("Initial baseline data populated successfully.")
    else:
        logger.info(f"Database contains {tenders_count} existing tender documents.")

    yield

    # Shutdown sequence
    logger.info("Indic Tender Platform shutting down gracefully.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Independent Indian Government Tender Data Platform - CPPP Public Intelligence",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for open data access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(health_router)
app.include_router(tenders_router)
app.include_router(ingest_router)

# Mount Static Files
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Indic Tender Platform API active. Navigate to /docs for OpenAPI specifications."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
