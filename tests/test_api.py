import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["safe_crawler_policy"]["captcha_bypass_allowed"] is False
    assert data["safe_crawler_policy"]["authentication_required"] is False


def test_api_list_tenders_and_filters(client):
    # Ensure baseline data is present
    client.post("/api/ingest/run", json={"mode": "FIXTURE_SNAPSHOT"})

    # 1. Basic listing
    response = client.get("/api/tenders")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 8

    # 2. Filter by Category
    res_works = client.get("/api/tenders?category=Works")
    assert res_works.status_code == 200
    works_data = res_works.json()
    assert all(item["tender_category"] == "Works" for item in works_data["items"])

    # 3. Search query
    res_search = client.get("/api/tenders?query=AIIMS")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert len(search_data["items"]) >= 1
    assert any("AIIMS" in item["source_tender_id"] or "AIIMS" in item["title"] for item in search_data["items"])


def test_api_single_tender_detail(client):
    # Fetch first tender from list
    res = client.get("/api/tenders?limit=1")
    items = res.json()["items"]
    assert len(items) > 0
    tender_id = items[0]["id"]

    res_detail = client.get(f"/api/tenders/{tender_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == tender_id
    assert "source_tender_id" in detail
    assert "organisation_chain" in detail
    assert "content_hash" in detail


def test_api_platform_stats(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_tenders"] >= 8
    assert stats["active_tenders"] >= 0
    assert "categories_breakdown" in stats
    assert "top_ministries" in stats


def test_api_ingestion_trigger_and_audit(client):
    # Trigger snapshot ingestion
    res_run = client.post("/api/ingest/run", json={"mode": "FIXTURE_SNAPSHOT"})
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert "run" in run_data
    run_id = run_data["run"]["run_id"]

    # Inspect runs list
    res_list = client.get("/api/ingest/runs")
    assert res_list.status_code == 200
    runs = res_list.json()
    assert any(r["run_id"] == run_id for r in runs)

    # Inspect single run detail
    res_single = client.get(f"/api/ingest/runs/{run_id}")
    assert res_single.status_code == 200
    single_run = res_single.json()
    assert single_run["run_id"] == run_id
    assert len(single_run.get("logs", [])) > 0


def test_api_export_csv(client):
    response = client.get("/api/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    content = response.text
    assert "Source,Tender ID,Reference Number,Title" in content
    assert "CPPP" in content
