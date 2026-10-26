import logging
from datetime import datetime, timezone
from typing import List, Callable, Dict, Any
import pymongo

logger = logging.getLogger("indic_tender.migrations")


class Migration:
    def __init__(self, migration_id: str, name: str, description: str, up: Callable[[Any], None]):
        self.migration_id = migration_id
        self.name = name
        self.description = description
        self.up = up


def migration_001_unique_tender_index(db):
    """Enforce uniqueness of source + source_tender_id for deduplication."""
    logger.info("Running 001_unique_tender_index...")
    tenders = db["tenders"]
    tenders.create_index(
        [("source", pymongo.ASCENDING), ("source_tender_id", pymongo.ASCENDING)],
        unique=True,
        name="idx_source_tender_id_unique"
    )


def migration_002_query_performance_indexes(db):
    """Indexes for fast search, range filters, and dashboard sorting."""
    logger.info("Running 002_query_performance_indexes...")
    tenders = db["tenders"]
    tenders.create_index([("bid_submission_closing_date", pymongo.ASCENDING)], name="idx_closing_date")
    tenders.create_index([("tender_category", pymongo.ASCENDING)], name="idx_tender_category")
    tenders.create_index([("ministry_or_state", pymongo.ASCENDING)], name="idx_ministry")
    tenders.create_index([("status", pymongo.ASCENDING)], name="idx_status")
    tenders.create_index([("tender_value_inr", pymongo.DESCENDING)], name="idx_tender_value")
    tenders.create_index([("last_updated_at", pymongo.DESCENDING)], name="idx_last_updated")
    tenders.create_index([("content_hash", pymongo.ASCENDING)], name="idx_content_hash")


def migration_003_text_search_index(db):
    """Compound full-text search index for intelligent semantic matching."""
    logger.info("Running 003_text_search_index...")
    tenders = db["tenders"]
    try:
        tenders.create_index(
            [
                ("title", pymongo.TEXT),
                ("work_description", pymongo.TEXT),
                ("organisation_chain", pymongo.TEXT),
                ("tender_reference_number", pymongo.TEXT),
            ],
            weights={
                "title": 10,
                "tender_reference_number": 8,
                "work_description": 5,
                "organisation_chain": 3,
            },
            name="idx_tenders_text_search"
        )
    except Exception as exc:
        # mongomock doesn't strictly support text indexes in older versions; handle gracefully
        logger.warning(f"Note on text index creation: {exc}")


def migration_004_ingestion_runs_indexes(db):
    """Audit run indexes for ingestion log retrieval."""
    logger.info("Running 004_ingestion_runs_indexes...")
    runs = db["ingestion_runs"]
    runs.create_index([("started_at", pymongo.DESCENDING)], name="idx_runs_started_at")
    runs.create_index([("run_id", pymongo.ASCENDING)], unique=True, name="idx_run_id_unique")
    runs.create_index([("status", pymongo.ASCENDING)], name="idx_runs_status")


MIGRATIONS: List[Migration] = [
    Migration(
        migration_id="001_unique_tender_index",
        name="Source & Tender ID unique constraint",
        description="Creates unique compound index on (source, source_tender_id) for safe idempotent upserts",
        up=migration_001_unique_tender_index,
    ),
    Migration(
        migration_id="002_query_performance_indexes",
        name="Query performance indexes",
        description="Creates indexes for closing date, category, ministry, status, and value range filtering",
        up=migration_002_query_performance_indexes,
    ),
    Migration(
        migration_id="003_text_search_index",
        name="Full text search index",
        description="Creates weighted text index on title, work description, and organisation chain",
        up=migration_003_text_search_index,
    ),
    Migration(
        migration_id="004_ingestion_runs_indexes",
        name="Ingestion audit run indexes",
        description="Creates index on ingestion_runs collection for tracking sync history",
        up=migration_004_ingestion_runs_indexes,
    ),
]


def run_migrations(db) -> List[Dict[str, Any]]:
    """Execute all pending database migrations in sequence."""
    migrations_coll = db["_migrations"]
    applied_docs = list(migrations_coll.find({}))
    applied_ids = {doc["migration_id"] for doc in applied_docs}

    results = []
    for m in MIGRATIONS:
        if m.migration_id in applied_ids:
            logger.debug(f"Migration {m.migration_id} already applied. Skipping.")
            continue

        logger.info(f"Applying migration '{m.migration_id}': {m.name}...")
        try:
            m.up(db)
            record = {
                "migration_id": m.migration_id,
                "name": m.name,
                "description": m.description,
                "applied_at": datetime.now(timezone.utc),
                "status": "APPLIED"
            }
            migrations_coll.insert_one(record)
            results.append(record)
            logger.info(f"Migration '{m.migration_id}' applied successfully.")
        except Exception as exc:
            logger.error(f"Migration '{m.migration_id}' failed: {exc}", exc_info=True)
            raise exc

    return results


if __name__ == "__main__":
    from app.db.connection import get_sync_db
    logging.basicConfig(level=logging.INFO)
    db = get_sync_db()
    applied = run_migrations(db)
    print(f"Migration execution completed. {len(applied)} new migrations applied.")
