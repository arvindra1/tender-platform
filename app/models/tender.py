from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TenderRevision(BaseModel):
    version: int
    changed_at: datetime
    previous_hash: str
    changes: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = "Corrigendum or field revision"


class TenderBase(BaseModel):
    source: str = Field(default="CPPP", description="Portal source identifier")
    source_tender_id: str = Field(..., description="Unique CPPP tender ID, e.g. 2026_CPPP_102938_1")
    tender_reference_number: str = Field(..., description="Tender Reference Number / NIT reference")
    title: str = Field(..., description="Title / Summary of the tender")
    work_description: Optional[str] = Field(default=None, description="Detailed scope of work / item description")
    
    # Hierarchy & classification
    organisation_chain: str = Field(..., description="Full organisational hierarchy chain")
    ministry_or_state: str = Field(..., description="Root Ministry, State Government, or Central PSU")
    department: Optional[str] = Field(default=None, description="Sub-department or division")
    tender_category: str = Field(default="Works", description="Works, Goods, Services, or Other")
    product_category: Optional[str] = Field(default=None, description="Product / work category e.g. Civil Works, IT")
    tender_type: str = Field(default="Open Tender", description="Open Tender, Limited, Single, EOI, etc.")
    
    # Financial fields
    tender_value_inr: Optional[float] = Field(default=None, description="Numeric tender value in INR")
    tender_value_display: Optional[str] = Field(default=None, description="Formatted string display e.g. ₹ 4,50,00,000")
    emd_amount_inr: Optional[float] = Field(default=None, description="Earnest Money Deposit amount in INR")
    emd_exemption_allowed: bool = Field(default=False, description="Whether EMD exemption is permitted")
    tender_fee_inr: Optional[float] = Field(default=None, description="Tender document fee in INR")
    fee_exemption_allowed: bool = Field(default=False, description="Whether tender fee exemption is permitted")
    
    # Critical dates
    tender_published_date: Optional[datetime] = Field(default=None, description="Date when tender was published")
    bid_submission_start_date: Optional[datetime] = Field(default=None, description="Bid submission start timestamp")
    bid_submission_closing_date: Optional[datetime] = Field(default=None, description="Bid submission deadline")
    bid_opening_date: Optional[datetime] = Field(default=None, description="Technical bid opening timestamp")
    
    # Location & portal references
    location: Optional[str] = Field(default=None, description="City / Region / Location")
    pincode: Optional[str] = Field(default=None, description="Postal pincode")
    corrigenda_count: int = Field(default=0, description="Total corrigenda / addenda published")
    source_url: str = Field(..., description="Public CPPP portal URL")
    nit_document_url: Optional[str] = Field(default=None, description="Notice Inviting Tender document link")


class TenderCreate(TenderBase):
    pass


class TenderInDB(TenderBase):
    id: Optional[str] = Field(default=None, alias="_id")
    content_hash: str = Field(..., description="SHA-256 fingerprint for deduplication")
    version: int = Field(default=1, description="Sequential document version")
    status: Literal["ACTIVE", "CLOSING_SOON", "CLOSED", "CORRIGENDUM_ISSUED"] = Field(
        default="ACTIVE", description="Computed operational status"
    )
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)
    last_updated_at: datetime = Field(default_factory=utc_now)
    history: List[TenderRevision] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True
    }


class TenderFilterParams(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    ministry: Optional[str] = None
    status: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    closing_before: Optional[datetime] = None
    closing_after: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=5000)
    sort_by: str = Field(default="bid_submission_closing_date")
    sort_order: Literal["asc", "desc"] = Field(default="asc")


class IngestionRun(BaseModel):
    run_id: str
    source: str = "CPPP"
    mode: str = "LIVE"
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    status: Literal["RUNNING", "COMPLETED", "FAILED"] = "RUNNING"
    items_extracted: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_unmodified: int = 0
    errors: List[str] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    duration_ms: Optional[float] = None



class PlatformStats(BaseModel):
    total_tenders: int
    active_tenders: int
    closing_soon_tenders: int
    corrigendum_tenders: int
    total_portfolio_value_inr: float
    total_portfolio_value_cr: float
    categories_breakdown: Dict[str, int]
    top_ministries: List[Dict[str, Any]]
    latest_sync_time: Optional[datetime] = None
