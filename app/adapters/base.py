import abc
import hashlib
import json
import logging
import time
from typing import List, Optional, Dict, Any
import httpx
from app.config import settings
from app.models.tender import TenderCreate

logger = logging.getLogger("indic_tender.adapter.base")


class BaseAdapter(abc.ABC):
    """
    Base class for Indian government tender portal adapters.
    
    Adheres strictly to safe public access:
    - No CAPTCHA bypassing
    - No authentication requirements (public listings only)
    - Configurable rate limiting and exponential backoff
    - Polite user-agent declaration
    """

    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self._last_request_time = 0.0
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": settings.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            }
            self._client = httpx.Client(
                headers=headers,
                timeout=settings.SAFE_TIMEOUT_SEC,
                follow_redirects=True,
            )
        return self._client

    def _rate_limit_wait(self):
        """Enforce polite rate limiting between external network requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < settings.SAFE_REQUEST_DELAY_SEC:
            sleep_time = settings.SAFE_REQUEST_DELAY_SEC - elapsed
            logger.debug(f"Polite rate limit: sleeping for {sleep_time:.2f}s before accessing {self.source_name}")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def safe_get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[httpx.Response]:
        """Safely fetch a public URL with retry and polite delay. Never bypasses CAPTCHAs."""
        self._rate_limit_wait()
        for attempt in range(1, settings.SAFE_MAX_RETRIES + 1):
            try:
                logger.info(f"Safe public fetch: GET {url} (Attempt {attempt}/{settings.SAFE_MAX_RETRIES})")
                response = self.client.get(url, params=params)
                
                # Check for standard CAPTCHA or blocking responses
                if "captcha" in response.text.lower() and response.status_code != 200:
                    logger.warning(f"Public page at {url} requires CAPTCHA verification. Safe access halts here.")
                    return None

                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} fetching {url}: {e}")
                if attempt == settings.SAFE_MAX_RETRIES:
                    raise
                time.sleep(attempt * 2.0)
            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.warning(f"Network error on {url}: {e}")
                if attempt == settings.SAFE_MAX_RETRIES:
                    raise
                time.sleep(attempt * 2.0)
        return None

    @staticmethod
    def compute_content_hash(tender: TenderCreate) -> str:
        """
        Compute deterministic SHA-256 fingerprint of tender content.
        Used for intelligent deduplication and change detection across runs.
        """
        normalized_data = {
            "source": tender.source.strip().upper(),
            "source_tender_id": tender.source_tender_id.strip(),
            "tender_reference_number": tender.tender_reference_number.strip(),
            "title": tender.title.strip(),
            "work_description": (tender.work_description or "").strip(),
            "organisation_chain": tender.organisation_chain.strip(),
            "tender_category": tender.tender_category.strip(),
            "product_category": (tender.product_category or "").strip(),
            "tender_type": tender.tender_type.strip(),
            "tender_value_inr": tender.tender_value_inr,
            "emd_amount_inr": tender.emd_amount_inr,
            "tender_fee_inr": tender.tender_fee_inr,
            "closing_date": tender.bid_submission_closing_date.isoformat() if tender.bid_submission_closing_date else None,
            "opening_date": tender.bid_opening_date.isoformat() if tender.bid_opening_date else None,
            "corrigenda_count": tender.corrigenda_count,
        }
        raw_json = json.dumps(normalized_data, sort_keys=True)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    @abc.abstractmethod
    def extract_public_listings(self, mode: str = "LIVE") -> List[TenderCreate]:
        """Extract public tender listings from the government portal."""
        pass

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()
