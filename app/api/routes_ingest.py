from typing import Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/api/ingest", tags=["Ingestion & Sync"])
ingestion_service = IngestionService()


class IngestTriggerRequest(BaseModel):
    mode: Literal["LIVE", "FIXTURE_SNAPSHOT"] = Field(
        default="LIVE",
        description="Ingestion execution mode: LIVE (safe web extraction with fallback) or FIXTURE_SNAPSHOT (deterministic)"
    )


@router.post("/run", summary="Trigger CPPP public tender extraction and deduplication")
def trigger_ingestion(payload: IngestTriggerRequest):
    """
    Execute extraction run for Central Public Procurement Portal (CPPP).
    Performs field normalization, SHA-256 deduplication, and revision tracking.
    """
    run_record = ingestion_service.run_cppp_ingestion(mode=payload.mode)
    return {
        "message": f"CPPP ingestion completed with status: {run_record.status}",
        "run": run_record
    }


@router.get("/runs", summary="List recent ingestion execution history")
def list_ingestion_runs(limit: int = 15):
    return ingestion_service.list_ingestion_runs(limit=limit)


@router.get("/runs/{run_id}", summary="Get audit logs for a specific ingestion run")
def get_ingestion_run(run_id: str):
    run = ingestion_service.get_ingestion_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Ingestion run '{run_id}' not found")
    return run
