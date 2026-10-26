import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from app.adapters.base import BaseAdapter
from app.adapters.cppp import CPPPAdapter
from app.db.connection import get_sync_db
from app.models.tender import (
    TenderCreate,
    TenderInDB,
    TenderRevision,
    IngestionRun,
    utc_now,
)

logger = logging.getLogger("indic_tender.service.ingestion")


class IngestionService:
    """
    Ingestion & Deduplication Service.
    
    Guarantees:
    - Safe idempotent upserts by compound key (source, source_tender_id).
    - SHA-256 content fingerprinting to distinguish unchanged vs modified tenders.
    - Full revision history audit trail when changes/corrigenda are detected.
    - Ingestion run tracking for observability and operational metrics.
    """

    def __init__(self, db=None):
        self.db = db or get_sync_db()
        self.adapter = CPPPAdapter()

    def _determine_status(self, closing_date: Optional[datetime], corrigenda_count: int) -> str:
        """Compute operational lifecycle status based on closing deadline and corrigenda."""
        now = utc_now()
        if closing_date:
            # Ensure timezone awareness
            if closing_date.tzinfo is None:
                closing_date = closing_date.replace(tzinfo=timezone.utc)
            if closing_date < now:
                return "CLOSED"
            if closing_date - now <= timedelta(days=7):
                return "CLOSING_SOON"

        if corrigenda_count > 0:
            return "CORRIGENDUM_ISSUED"

        return "ACTIVE"

    def _calculate_diff(self, old_doc: Dict[str, Any], new_tender: TenderCreate) -> Dict[str, Any]:
        """Compute field-level changes between existing document and new extraction."""
        diff = {}
        fields_to_check = [
            "title",
            "tender_value_inr",
            "emd_amount_inr",
            "bid_submission_closing_date",
            "bid_opening_date",
            "corrigenda_count",
            "location",
            "tender_category",
        ]
        for field in fields_to_check:
            old_val = old_doc.get(field)
            new_val = getattr(new_tender, field, None)
            
            # Format datetime for comparison
            if isinstance(old_val, datetime):
                old_val_cmp = old_val.isoformat()
            else:
                old_val_cmp = old_val

            if isinstance(new_val, datetime):
                new_val_cmp = new_val.isoformat()
            else:
                new_val_cmp = new_val

            if old_val_cmp != new_val_cmp:
                diff[field] = {
                    "previous": old_val_cmp,
                    "new": new_val_cmp
                }
        return diff

    def run_cppp_ingestion(self, mode: str = "LIVE") -> IngestionRun:
        """
        Execute CPPP extraction, deduplication, and storage pipeline.
        
        mode:
        - "LIVE": Queries public CPPP portal with safe fallback to snapshot.
        - "FIXTURE_SNAPSHOT": Runs deterministic local snapshot ingestion.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        start_time = utc_now()
        start_perf = time.perf_counter()

        run = IngestionRun(
            run_id=run_id,
            source="CPPP",
            mode=mode,
            started_at=start_time,
            status="RUNNING"
        )
        self.db["ingestion_runs"].insert_one(run.model_dump())

        logs: List[str] = []
        errors: List[str] = []
        created_count = 0
        updated_count = 0
        unmodified_count = 0

        def log_msg(msg: str):
            logger.info(f"[{run_id}] {msg}")
            logs.append(f"[{utc_now().strftime('%H:%M:%S')}] {msg}")

        log_msg(f"Starting CPPP ingestion run (Mode: {mode})")

        try:
            # 1. Extraction from public listings
            extracted_tenders = self.adapter.extract_public_listings(mode=mode)
            run.items_extracted = len(extracted_tenders)
            log_msg(f"Extracted {len(extracted_tenders)} public tender listings from CPPP")

            tenders_coll = self.db["tenders"]

            # 2. Process each tender with deduplication and change tracking
            for tender in extracted_tenders:
                content_hash = BaseAdapter.compute_content_hash(tender)
                computed_status = self._determine_status(
                    tender.bid_submission_closing_date,
                    tender.corrigenda_count
                )

                # Search existing document by natural compound key
                existing = tenders_coll.find_one({
                    "source": tender.source,
                    "source_tender_id": tender.source_tender_id
                })

                now = utc_now()

                if existing is None:
                    # Case A: Brand new tender
                    new_doc = TenderInDB(
                        **tender.model_dump(),
                        content_hash=content_hash,
                        version=1,
                        status=computed_status,
                        first_seen_at=now,
                        last_seen_at=now,
                        last_updated_at=now,
                        history=[]
                    )
                    tenders_coll.insert_one(new_doc.model_dump(by_alias=True, exclude={"id"}))
                    created_count += 1
                    log_msg(f"CREATED: {tender.source_tender_id} - '{tender.title[:45]}...'")

                elif existing.get("content_hash") == content_hash:
                    # Case B: Exists and unmodified
                    tenders_coll.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {
                                "last_seen_at": now,
                                "status": computed_status  # status may change due to time passing
                            }
                        }
                    )
                    unmodified_count += 1
                    log_msg(f"UNMODIFIED: {tender.source_tender_id} (last seen refreshed)")

                else:
                    # Case C: Exists but modified (Corrigendum / Extension / Date / Value change)
                    diff = self._calculate_diff(existing, tender)
                    old_version = existing.get("version", 1)
                    new_version = old_version + 1

                    revision = TenderRevision(
                        version=old_version,
                        changed_at=now,
                        previous_hash=existing.get("content_hash", ""),
                        changes=diff,
                        reason="CPPP Listing Corrigendum or Field Modification"
                    )

                    update_fields = tender.model_dump()
                    update_fields.update({
                        "content_hash": content_hash,
                        "version": new_version,
                        "status": computed_status,
                        "last_seen_at": now,
                        "last_updated_at": now,
                    })

                    tenders_coll.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": update_fields,
                            "$push": {"history": revision.model_dump()}
                        }
                    )
                    updated_count += 1
                    log_msg(f"UPDATED: {tender.source_tender_id} (Version {old_version} -> {new_version})")

            # 3. Finalize run statistics
            duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
            log_msg(
                f"Ingestion completed in {duration_ms}ms. "
                f"Created: {created_count}, Updated: {updated_count}, Unmodified: {unmodified_count}"
            )

            run.completed_at = utc_now()
            run.status = "COMPLETED"
            run.items_created = created_count
            run.items_updated = updated_count
            run.items_unmodified = unmodified_count
            run.duration_ms = duration_ms
            run.logs = logs
            run.errors = errors

            self.db["ingestion_runs"].update_one(
                {"run_id": run_id},
                {"$set": run.model_dump()}
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
            error_str = f"Ingestion run failed: {str(exc)}"
            logger.error(error_str, exc_info=True)
            errors.append(error_str)
            logs.append(f"[{utc_now().strftime('%H:%M:%S')}] ERROR: {error_str}")

            run.completed_at = utc_now()
            run.status = "FAILED"
            run.duration_ms = duration_ms
            run.errors = errors
            run.logs = logs

            self.db["ingestion_runs"].update_one(
                {"run_id": run_id},
                {"$set": run.model_dump()}
            )

        return run

    def list_ingestion_runs(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieve recent ingestion run audit history."""
        cursor = self.db["ingestion_runs"].find().sort("started_at", -1).limit(limit)
        runs = []
        for doc in cursor:
            doc["_id"] = str(doc.get("_id", ""))
            runs.append(doc)
        return runs

    def get_ingestion_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve details of a specific ingestion run."""
        doc = self.db["ingestion_runs"].find_one({"run_id": run_id})
        if doc:
            doc["_id"] = str(doc.get("_id", ""))
        return doc
