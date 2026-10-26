import csv
import io
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import re

from bson import ObjectId
from app.db.connection import get_sync_db
from app.models.tender import TenderFilterParams, PlatformStats, utc_now

logger = logging.getLogger("indic_tender.service.tenders")


class TenderService:
    def __init__(self, db=None):
        self.db = db or get_sync_db()

    def _build_filter_query(self, params: TenderFilterParams) -> Dict[str, Any]:
        """Construct MongoDB query dictionary from filter parameters."""
        query: Dict[str, Any] = {}

        # 1. Text Search or Keyword matching
        if params.query and params.query.strip():
            clean_q = params.query.strip()
            # If search term has multiple words or special chars, regex search across key fields
            escaped_q = re.escape(clean_q)
            query["$or"] = [
                {"title": {"$regex": escaped_q, "$options": "i"}},
                {"tender_reference_number": {"$regex": escaped_q, "$options": "i"}},
                {"source_tender_id": {"$regex": escaped_q, "$options": "i"}},
                {"organisation_chain": {"$regex": escaped_q, "$options": "i"}},
                {"product_category": {"$regex": escaped_q, "$options": "i"}},
                {"location": {"$regex": escaped_q, "$options": "i"}},
            ]

        # 2. Category
        if params.category and params.category.strip() and params.category.lower() != "all":
            query["tender_category"] = {"$regex": f"^{params.category.strip()}$", "$options": "i"}

        # 3. Ministry
        if params.ministry and params.ministry.strip() and params.ministry.lower() != "all":
            query["ministry_or_state"] = {"$regex": re.escape(params.ministry.strip()), "$options": "i"}

        # 4. Status
        if params.status and params.status.strip() and params.status.lower() != "all":
            query["status"] = params.status.strip().upper()

        # 5. Value ranges
        if params.min_value is not None or params.max_value is not None:
            val_filter = {}
            if params.min_value is not None:
                val_filter["$gte"] = params.min_value
            if params.max_value is not None:
                val_filter["$lte"] = params.max_value
            query["tender_value_inr"] = val_filter

        # 6. Closing date bounds
        if params.closing_before is not None or params.closing_after is not None:
            date_filter = {}
            if params.closing_after is not None:
                date_filter["$gte"] = params.closing_after
            if params.closing_before is not None:
                date_filter["$lte"] = params.closing_before
            query["bid_submission_closing_date"] = date_filter

        return query

    def list_tenders(self, params: TenderFilterParams) -> Dict[str, Any]:
        """Query tenders collection with filtering, sorting, and pagination."""
        query = self._build_filter_query(params)
        coll = self.db["tenders"]

        total_count = coll.count_documents(query)

        # Determine sort direction
        direction = 1 if params.sort_order == "asc" else -1
        sort_field = params.sort_by or "bid_submission_closing_date"

        skip = (params.page - 1) * params.limit
        cursor = coll.find(query).sort(sort_field, direction).skip(skip).limit(params.limit)

        items = []
        for doc in cursor:
            doc["id"] = str(doc.get("_id", ""))
            doc.pop("_id", None)
            items.append(doc)

        total_pages = max(1, (total_count + params.limit - 1) // params.limit)

        return {
            "total": total_count,
            "page": params.page,
            "limit": params.limit,
            "total_pages": total_pages,
            "items": items,
        }

    def get_tender_by_id(self, tender_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tender by MongoDB ObjectId or source_tender_id."""
        coll = self.db["tenders"]
        doc = None

        if ObjectId.is_valid(tender_id):
            doc = coll.find_one({"_id": ObjectId(tender_id)})

        if not doc:
            doc = coll.find_one({"source_tender_id": tender_id})

        if doc:
            doc["id"] = str(doc.get("_id", ""))
            doc.pop("_id", None)
            return doc
        return None

    def get_platform_stats(self) -> PlatformStats:
        """Compute live dashboard analytics from MongoDB storage."""
        coll = self.db["tenders"]
        now = utc_now()

        total_tenders = coll.count_documents({})
        if total_tenders == 0:
            return PlatformStats(
                total_tenders=0,
                active_tenders=0,
                closing_soon_tenders=0,
                corrigendum_tenders=0,
                total_portfolio_value_inr=0.0,
                total_portfolio_value_cr=0.0,
                categories_breakdown={},
                top_ministries=[],
                latest_sync_time=None,
            )

        # Active, closing soon, corrigenda counts
        active_count = coll.count_documents({"status": {"$in": ["ACTIVE", "CLOSING_SOON", "CORRIGENDUM_ISSUED"]}})
        closing_soon_count = coll.count_documents({"status": "CLOSING_SOON"})
        corrigendum_count = coll.count_documents({"status": "CORRIGENDUM_ISSUED"})

        # Financial aggregation
        total_val_inr = 0.0
        docs = coll.find({"tender_value_inr": {"$ne": None}}, {"tender_value_inr": 1})
        for d in docs:
            v = d.get("tender_value_inr")
            if isinstance(v, (int, float)):
                total_val_inr += v

        total_val_cr = round(total_val_inr / 10_000_000, 2)

        # Category breakdown
        cat_counts = {}
        for cat in ["Works", "Goods", "Services"]:
            cat_counts[cat] = coll.count_documents({"tender_category": cat})

        # Top ministries
        ministries = coll.distinct("ministry_or_state")
        top_ministries = []
        for m in ministries[:6]:
            if not m:
                continue
            m_count = coll.count_documents({"ministry_or_state": m})
            top_ministries.append({"ministry": m, "count": m_count})
        top_ministries.sort(key=lambda x: x["count"], reverse=True)

        # Latest sync
        latest_run = self.db["ingestion_runs"].find_one(
            {"status": "COMPLETED"},
            sort=[("started_at", -1)]
        )
        latest_sync = latest_run.get("started_at") if latest_run else None

        return PlatformStats(
            total_tenders=total_tenders,
            active_tenders=active_count,
            closing_soon_tenders=closing_soon_count,
            corrigendum_tenders=corrigendum_count,
            total_portfolio_value_inr=round(total_val_inr, 2),
            total_portfolio_value_cr=total_val_cr,
            categories_breakdown=cat_counts,
            top_ministries=top_ministries,
            latest_sync_time=latest_sync,
        )

    def get_filter_options(self) -> Dict[str, Any]:
        """Retrieve distinct options for UI filter dropdowns."""
        coll = self.db["tenders"]
        ministries = sorted([m for m in coll.distinct("ministry_or_state") if m])
        categories = sorted([c for c in coll.distinct("tender_category") if c])
        statuses = ["ACTIVE", "CLOSING_SOON", "CORRIGENDUM_ISSUED", "CLOSED"]
        return {
            "ministries": ministries,
            "categories": categories,
            "statuses": statuses
        }

    def export_csv(self, params: TenderFilterParams) -> str:
        """Export filtered tenders as standard CSV string."""
        params.page = 1
        params.limit = 5000  # maximum export batch
        results = self.list_tenders(params)

        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "Source",
            "Tender ID",
            "Reference Number",
            "Title",
            "Ministry / State",
            "Department",
            "Category",
            "Product Category",
            "Value (INR)",
            "Value Display",
            "EMD (INR)",
            "Bid Closing Date",
            "Bid Opening Date",
            "Location",
            "Pincode",
            "Status",
            "Corrigenda Count",
            "Version",
            "Public Source URL"
        ]
        writer.writerow(headers)

        for t in results["items"]:
            writer.writerow([
                t.get("source", "CPPP"),
                t.get("source_tender_id", ""),
                t.get("tender_reference_number", ""),
                t.get("title", ""),
                t.get("ministry_or_state", ""),
                t.get("department", ""),
                t.get("tender_category", ""),
                t.get("product_category", ""),
                t.get("tender_value_inr", ""),
                t.get("tender_value_display", ""),
                t.get("emd_amount_inr", ""),
                t.get("bid_submission_closing_date", ""),
                t.get("bid_opening_date", ""),
                t.get("location", ""),
                t.get("pincode", ""),
                t.get("status", ""),
                t.get("corrigenda_count", 0),
                t.get("version", 1),
                t.get("source_url", "")
            ])

        return output.getvalue()
