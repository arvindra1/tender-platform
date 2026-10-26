# 🏛️ IndicTender Platform: CPPP Public Tender Intelligence

An independent, production-ready data intelligence platform and web application for Indian government public procurement, starting with the **Central Public Procurement Portal (CPPP - eprocure.gov.in)**.

Built with Python source adapters, safe public access compliance, SHA-256 deduplication, schema versioning/migrations, MongoDB storage, an analytics dashboard, and automated test coverage.

---

## 📌 Milestone Overview & Extraction Scope

### Source 1: Central Public Procurement Portal (CPPP)
The extraction scope captures **all public listing fields** published across Ministries, Departments, and Central Public Sector Undertakings (CPSUs):

| Domain Field | Description | Type / Example |
|---|---|---|
| `source` | Portal Source Identifier | `"CPPP"` |
| `source_tender_id` | Unique Portal Tender ID | e.g. `2026_AIIMS_102938_1` |
| `tender_reference_number` | Official NIT / Reference Code | e.g. `AIIMS/PROC/RAD/2026/089` |
| `title` | Work Title / Project Description | Full procurement title string |
| `work_description` | Expanded scope of work | Contextual description |
| `organisation_chain` | Hierarchical procuring chain | `Ministry \|\| Dept \|\| Division` |
| `ministry_or_state` | Root ministry or state authority | e.g. `Ministry of Health and Family Welfare` |
| `department` | Sub-entity / Procuring office | e.g. `AIIMS New Delhi` |
| `tender_category` | Category classification | `Works`, `Goods`, `Services` |
| `product_category` | Specialized product / industry domain | e.g. `Medical Equipment`, `Civil Works` |
| `tender_type` | Procurement modality | `Open Tender`, `Limited Tender`, `EOI` |
| `tender_value_inr` | Estimated monetary value in INR | Float value (e.g. `185000000.0`) |
| `tender_value_display` | Indian numerical formatting | e.g. `₹ 18.50 Cr` or `₹ 75.00 Lakhs` |
| `emd_amount_inr` | Earnest Money Deposit | Float value (e.g. `3700000.0`) |
| `emd_exemption_allowed` | Exemption status indicator | Boolean |
| `tender_fee_inr` | Document fee | Float / None |
| `tender_published_date` | Date of portal publication | UTC ISO Timestamp |
| `bid_submission_start_date` | Bid submission start date | UTC ISO Timestamp |
| `bid_submission_closing_date` | Submission deadline (Due date) | UTC ISO Timestamp |
| `bid_opening_date` | Technical bid opening date | UTC ISO Timestamp |
| `location` & `pincode` | Execution site & 6-digit PIN | e.g. `New Delhi - 110029` |
| `corrigenda_count` | Number of amendments / extensions | Integer |
| `source_url` | Direct public portal link | `https://eprocure.gov.in/...` |
| `nit_document_url` | Notice Inviting Tender doc link | URL string |
| `content_hash` | SHA-256 fingerprint for deduplication | Hex digest string |
| `version` | Document revision counter | Integer (starts at 1) |
| `status` | Operational lifecycle status | `ACTIVE`, `CLOSING_SOON`, `CORRIGENDUM_ISSUED`, `CLOSED` |
| `history` | Change audit log & field diffs | Array of past version snapshots |

---

## 🛡️ Safe Public Access Policy

This platform strictly adheres to ethical, legal, and non-intrusive public data extraction guidelines:
1. **Zero CAPTCHA Bypassing**: The system never attempts to bypass or break CAPTCHAs. If a page enforces a CAPTCHA barrier, access is aborted safely.
2. **No Authentication Required**: Only strictly public listing pages and active feeds are crawled; no login credentials or session spoofing are used.
3. **Polite Crawling & Rate Limiting**: Enforces a polite minimum delay (`SAFE_REQUEST_DELAY_SEC = 1.5s`) between external requests with exponential backoff on retries.
4. **Transparent User-Agent**: Declares an identifiable User-Agent (`IndicTenderPlatform/1.0 (+https://github.com/indic-tender/crawler)`).
5. **Deterministic Offline Snapshot Fallback**: When government endpoints are offline, rate-limiting, or behind geo-blocks, the system transparently utilizes certified snapshot fixtures so that testing and pipelines remain operational.

---

## 🔄 Intelligent Deduplication & Revision Tracking

Indian government tenders frequently undergo extensions, corrigenda, or financial amendments before bid opening. The deduplication engine guarantees idempotency and tracks updates:

1. **Natural Compound Key**: Every tender is uniquely identified by `(source, source_tender_id)`.
2. **Deterministic SHA-256 Content Fingerprint**: Computes a stable hash across normalized core fields (title, dates, values, corrigenda count, organisation).
3. **Execution States**:
   - **`CREATED`**: New tender encountered. Initialized with `version = 1`, `history = []`, `first_seen_at = now`.
   - **`UNMODIFIED`**: Document exists and `content_hash` matches. The platform updates `last_seen_at = now` and recomputes deadline status without creating duplicate entries.
   - **`UPDATED`**: Document exists but `content_hash` differs (e.g. closing date extended or corrigendum issued).
     - Field-level diff is calculated (`diff = { "field": { "previous": ..., "new": ... } }`).
     - Previous version is archived into the `history` array.
     - Document fields are updated, `version` is incremented (`version = version + 1`), and `last_updated_at` is stamped.
4. **Ingestion Audit Runs**: Every execution is audited in `ingestion_runs` with items created, updated, and unmodified, along with execution time and logs.

---

## 🗄️ Database Architecture & Migrations

### Collections:
- `tenders`: Core document store holding tender records and revision histories.
- `ingestion_runs`: Observability audit store tracking extraction metrics, duration, and logs.
- `_migrations`: Registry of executed database migrations ensuring schema idempotency.

### Indexes Enforced via `app/db/migrations.py`:
- `idx_source_tender_id_unique`: Compound unique index on `[("source", 1), ("source_tender_id", 1)]`.
- `idx_closing_date`: Ascending index on `bid_submission_closing_date` for urgent deadline queries.
- `idx_tender_category`: Index on `tender_category` (Works, Goods, Services).
- `idx_ministry`: Index on `ministry_or_state` for departmental aggregation.
- `idx_status`: Index on operational status (`ACTIVE`, `CLOSING_SOON`, etc.).
- `idx_tender_value`: Descending index on `tender_value_inr` for high-value tenders.
- `idx_tenders_text_search`: Weighted compound text search index on `title`, `tender_reference_number`, `work_description`, and `organisation_chain`.
- `idx_runs_started_at`: Index on `ingestion_runs` for audit history ordering.

---

## 💻 Tech Stack & Architecture

- **Backend**: Python 3.9+, [FastAPI](https://fastapi.tiangolo.com/), [Pydantic v2](https://docs.pydantic.dev/), [httpx](https://www.python-httpx.org/), [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/).
- **Storage**: [MongoDB 7.0](https://www.mongodb.com/) via `pymongo` and `motor`. Includes a zero-configuration in-memory compatibility engine (`mongomock`) for immediate local execution when MongoDB is not running.
- **Frontend**: Modern Vanilla HTML5, CSS3, and JavaScript Single-Page Application (SPA) with dark/light themes, Tricolor design accents, live metrics, instant debounced search, category filters, detail modals, raw JSON inspection, and CSV export.
- **Testing**: [pytest](https://docs.pytest.org/), `pytest-asyncio`, `mongomock`, and FastAPI `TestClient`.

---

## 🚀 Runnable Setup Instructions

### Option 1: One-Command Local Startup (Fastest)

Clone or navigate to the directory and run:

```bash
chmod +x run.sh
./run.sh
```

`run.sh` automatically:
1. Creates a Python virtual environment in `./venv` (if not already present).
2. Installs all required dependencies from `requirements.txt`.
3. Checks and executes database migrations.
4. Starts the FastAPI server on `http://localhost:8000`.

Open your browser to:
- **Web Application Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI 3.0 Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **System Health & Policy Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### Option 2: Docker Compose (MongoDB 7 + Web Application)

To run the complete production stack including an official MongoDB container:

```bash
docker compose up --build
```

Services started:
- `indic_tender_mongodb`: MongoDB 7.0 daemon with persistent volume `mongo_data` on port `27017`.
- `indic_tender_webapp`: FastAPI application on port `8000`.

---

## 🧪 Running Automated Tests

Run the full automated test suite with coverage:

```bash
./venv/bin/pytest -v
```

### Test Suite Coverage:
- **`tests/test_cppp_adapter.py`**: Validates HTML parsing of CPPP listings, Indian currency parsing (`₹ 18,50,00,000`, `145 Cr`, `NA`), date formats, organization chain splitting, and pincode extraction.
- **`tests/test_deduplication.py`**: Verifies SHA-256 content fingerprinting, idempotency (zero modifications on repeated ingestion), and version increments with field diffs when amendments occur.
- **`tests/test_migrations.py`**: Verifies migration execution, index creation, and idempotency.
- **`tests/test_api.py`**: Validates `/api/health`, `/api/tenders`, `/api/stats`, `/api/ingest/run`, and `/api/export` CSV streaming.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check, uptime, and safe crawler policy metadata |
| `GET` | `/api/stats` | Aggregated analytics (Total count, Active count, Value in Cr, Top ministries) |
| `GET` | `/api/tenders` | Paginated listing with search, category, ministry, status, and date filters |
| `GET` | `/api/tenders/{id}` | Detailed tender record, timeline, corrigenda, and revision history |
| `GET` | `/api/filter-options`| Dynamic lists of available ministries, categories, and statuses |
| `GET` | `/api/export` | Download filtered tender results as CSV |
| `POST`| `/api/ingest/run` | Trigger CPPP extraction run (`{"mode": "LIVE" \| "FIXTURE_SNAPSHOT"}`) |
| `GET` | `/api/ingest/runs` | List past extraction audit runs and execution metrics |
| `GET` | `/api/ingest/runs/{run_id}` | Detailed execution logs and metrics for a specific run |

---

## 📂 Project Directory Structure

```
indic-tender-platform/
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Compose stack (MongoDB 7 + Web App)
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── run.sh                      # One-command executable runner
├── .env.example                # Environment variables template
├── README.md                   # Complete architectural documentation
├── app/
│   ├── config.py               # Pydantic BaseSettings & crawler rules
│   ├── main.py                 # FastAPI application, lifespan & routers
│   ├── models/
│   │   ├── __init__.py
│   │   └── tender.py           # Pydantic schemas (Tender, Revision, Run, Stats)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py       # Dual MongoDB & In-Memory fallback client
│   │   └── migrations.py       # Schema migration engine and indexes
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseAdapter (rate limits, safe get, SHA-256)
│   │   ├── cppp.py             # CPPP public listings parser
│   │   └── fixtures/
│   │       └── cppp_sample_listing.html # Authentic CPPP table fixture
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion_service.py# Deduplication, diffing & audit engine
│   │   └── tender_service.py   # Search, faceted filters, stats & CSV export
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_health.py    # /api/health
│   │   ├── routes_tenders.py   # /api/tenders, /api/stats, /api/export
│   │   └── routes_ingest.py    # /api/ingest/run, /api/ingest/runs
│   └── static/
│       ├── index.html          # Modern dashboard single-page interface
│       ├── css/
│       │   └── app.css         # Glassmorphism, animations, responsive grid
│       └── js/
│           └── app.js          # Client controller, search, filters & modals
└── tests/
    ├── __init__.py
    ├── test_cppp_adapter.py    # CPPP parsing & currency tests
    ├── test_deduplication.py   # Hashing, idempotency & diff tests
    ├── test_migrations.py      # Migration runner & index tests
    └── test_api.py             # FastAPI TestClient API tests
```
# tender-platform
