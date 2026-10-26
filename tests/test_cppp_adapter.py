import pytest
from datetime import datetime, timezone
from app.adapters.cppp import CPPPAdapter
from app.models.tender import TenderCreate


@pytest.fixture
def adapter():
    return CPPPAdapter()


def test_parse_indian_currency(adapter):
    # Test Indian comma separation
    assert adapter.parse_indian_currency("₹ 18,50,00,000") == 185000000.0
    assert adapter.parse_indian_currency("42,80,50,000") == 428050000.0
    
    # Test Crore / Lakh text
    assert adapter.parse_indian_currency("145.00 Cr") == 1450000000.0
    assert adapter.parse_indian_currency("₹ 75 Lakhs") == 7500000.0
    
    # Test Nil / NA / Unpriced
    assert adapter.parse_indian_currency("NA") is None
    assert adapter.parse_indian_currency("Nil") is None
    assert adapter.parse_indian_currency("-") is None
    assert adapter.parse_indian_currency("") is None


def test_format_inr_display(adapter):
    assert adapter.format_inr_display(185000000.0) == "₹ 18.50 Cr"
    assert adapter.format_inr_display(7500000.0) == "₹ 75.00 Lakhs"
    assert adapter.format_inr_display(45000.0) == "₹ 45,000.00"
    assert adapter.format_inr_display(None) == "Not Disclosed"


def test_parse_cppp_date(adapter):
    dt = adapter.parse_cppp_date("20-Oct-2026 09:00 AM")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 20
    assert dt.hour == 9
    assert dt.minute == 0
    assert dt.tzinfo == timezone.utc

    # Invalid / empty dates
    assert adapter.parse_cppp_date("NA") is None
    assert adapter.parse_cppp_date("") is None


def test_parse_org_hierarchy(adapter):
    chain = "Ministry of Health and Family Welfare || All India Institute of Medical Sciences (AIIMS) || AIIMS New Delhi"
    ministry, dept = adapter.parse_org_hierarchy(chain)
    assert ministry == "Ministry of Health and Family Welfare"
    assert dept == "All India Institute of Medical Sciences (AIIMS)"


def test_extract_from_fixture(adapter):
    tenders = adapter.extract_public_listings(mode="FIXTURE_SNAPSHOT")
    assert len(tenders) == 8

    # Verify first tender: AIIMS New Delhi
    aiims_tender = next(t for t in tenders if "AIIMS" in t.source_tender_id)
    assert aiims_tender.source == "CPPP"
    assert aiims_tender.source_tender_id == "2026_AIIMS_102938_1"
    assert aiims_tender.tender_reference_number == "AIIMS/PROC/RAD/2026/089"
    assert "MRI System" in aiims_tender.title
    assert aiims_tender.tender_category == "Goods"
    assert aiims_tender.product_category == "Medical Equipment"
    assert aiims_tender.tender_value_inr == 185000000.0
    assert aiims_tender.emd_amount_inr == 3700000.0
    assert aiims_tender.pincode == "110029"
    assert aiims_tender.corrigenda_count == 1
    assert "Ansari Nagar, New Delhi" in aiims_tender.location

    # Verify second tender: Northern Railway
    rail_tender = next(t for t in tenders if "RAIL" in t.source_tender_id)
    assert rail_tender.source_tender_id == "2026_RAIL_102939_1"
    assert rail_tender.tender_category == "Works"
    assert rail_tender.tender_value_inr == 428050000.0
    assert rail_tender.pincode == "244001"
