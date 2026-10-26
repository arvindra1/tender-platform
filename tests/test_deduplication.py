import mongomock
import pytest
from datetime import datetime, timezone, timedelta
from app.adapters.base import BaseAdapter
from app.models.tender import TenderCreate
from app.services.ingestion_service import IngestionService


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    return client["test_indic_tenders"]


def create_sample_tender(tender_id="2026_CPPP_TEST_1", value=1000000.0, corrigenda=0, closing_days=10):
    base_date = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    return TenderCreate(
        source="CPPP",
        source_tender_id=tender_id,
        tender_reference_number="REF-TEST-001",
        title="Procurement of Server Hardware for Data Center",
        work_description="Supply of 2U Rack Servers",
        organisation_chain="Ministry of Electronics and IT || NIC",
        ministry_or_state="Ministry of Electronics and IT",
        department="NIC",
        tender_category="Goods",
        product_category="IT Hardware",
        tender_type="Open Tender",
        tender_value_inr=value,
        tender_value_display="₹ 10.00 Lakhs",
        emd_amount_inr=20000.0,
        emd_exemption_allowed=True,
        tender_fee_inr=None,
        fee_exemption_allowed=False,
        tender_published_date=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
        bid_submission_start_date=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
        bid_submission_closing_date=base_date + timedelta(days=closing_days),
        bid_opening_date=base_date + timedelta(days=closing_days + 1),
        location="New Delhi",
        pincode="110003",
        corrigenda_count=corrigenda,
        source_url="https://eprocure.gov.in/eprocure/app?page=sample",
        nit_document_url=None
    )


def test_content_fingerprint_determinism():
    t1 = create_sample_tender()
    t2 = create_sample_tender()

    h1 = BaseAdapter.compute_content_hash(t1)
    h2 = BaseAdapter.compute_content_hash(t2)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex length

    # Changing any meaningful field modifies hash
    t3 = create_sample_tender(corrigenda=1)
    h3 = BaseAdapter.compute_content_hash(t3)
    assert h1 != h3


def test_ingestion_deduplication_lifecycle(mock_db):
    service = IngestionService(db=mock_db)
    
    # 1. First Run: Snapshot ingestion
    run1 = service.run_cppp_ingestion(mode="FIXTURE_SNAPSHOT")
    assert run1.status == "COMPLETED"
    assert run1.items_created == 8
    assert run1.items_updated == 0
    assert run1.items_unmodified == 0
    assert mock_db["tenders"].count_documents({}) == 8

    # Check document properties
    doc = mock_db["tenders"].find_one({"source_tender_id": "2026_AIIMS_102938_1"})
    assert doc is not None
    assert doc["version"] == 1
    assert len(doc.get("history", [])) == 0

    # 2. Second Run: Exactly identical data (Idempotency test)
    run2 = service.run_cppp_ingestion(mode="FIXTURE_SNAPSHOT")
    assert run2.status == "COMPLETED"
    assert run2.items_created == 0
    assert run2.items_updated == 0
    assert run2.items_unmodified == 8
    assert mock_db["tenders"].count_documents({}) == 8

    # 3. Third Run: Simulate Corrigendum / Field modification
    # Modify one tender in the database so that re-ingesting fixture triggers an update
    mock_db["tenders"].update_one(
        {"source_tender_id": "2026_AIIMS_102938_1"},
        {"$set": {"tender_value_inr": 999999.0, "content_hash": "modified_previous_hash"}}
    )

    run3 = service.run_cppp_ingestion(mode="FIXTURE_SNAPSHOT")
    assert run3.items_created == 0
    assert run3.items_updated == 1
    assert run3.items_unmodified == 7

    updated_doc = mock_db["tenders"].find_one({"source_tender_id": "2026_AIIMS_102938_1"})
    assert updated_doc["version"] == 2
    assert len(updated_doc["history"]) == 1
    assert updated_doc["history"][0]["version"] == 1
    assert "tender_value_inr" in updated_doc["history"][0]["changes"]
