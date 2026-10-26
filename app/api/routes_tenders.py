from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Query, HTTPException, Response
from fastapi.responses import PlainTextResponse

from app.models.tender import TenderFilterParams, PlatformStats
from app.services.tender_service import TenderService

router = APIRouter(prefix="/api", tags=["Tenders"])
tender_service = TenderService()


@router.get("/tenders", summary="List tenders with multi-faceted filtering")
def list_tenders(
    query: Optional[str] = Query(None, description="Search keyword in title, reference, org, or location"),
    category: Optional[str] = Query(None, description="Filter by tender category: Works, Goods, Services"),
    ministry: Optional[str] = Query(None, description="Filter by ministry or state authority"),
    status: Optional[str] = Query(None, description="Status: ACTIVE, CLOSING_SOON, CORRIGENDUM_ISSUED, CLOSED"),
    min_value: Optional[float] = Query(None, description="Minimum tender value in INR"),
    max_value: Optional[float] = Query(None, description="Maximum tender value in INR"),
    closing_before: Optional[datetime] = Query(None, description="Closing deadline upper bound"),
    closing_after: Optional[datetime] = Query(None, description="Closing deadline lower bound"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("bid_submission_closing_date", description="Field to sort by"),
    sort_order: Literal["asc", "desc"] = Query("asc", description="Sort direction")
):
    params = TenderFilterParams(
        query=query,
        category=category,
        ministry=ministry,
        status=status,
        min_value=min_value,
        max_value=max_value,
        closing_before=closing_before,
        closing_after=closing_after,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return tender_service.list_tenders(params)


@router.get("/tenders/{tender_id}", summary="Get comprehensive details for a single tender")
def get_tender(tender_id: str):
    tender = tender_service.get_tender_by_id(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender with ID '{tender_id}' not found")
    return tender


@router.get("/stats", response_model=PlatformStats, summary="Retrieve aggregate platform statistics")
def get_stats():
    return tender_service.get_platform_stats()


@router.get("/filter-options", summary="Get options for filter dropdowns")
def get_filter_options():
    return tender_service.get_filter_options()


@router.get("/export", summary="Export filtered tenders as CSV")
def export_tenders_csv(
    query: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    ministry: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
):
    params = TenderFilterParams(
        query=query,
        category=category,
        ministry=ministry,
        status=status,
        min_value=min_value,
        max_value=max_value,
        page=1,
        limit=5000
    )
    csv_data = tender_service.export_csv(params)
    filename = f"indic_tenders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
