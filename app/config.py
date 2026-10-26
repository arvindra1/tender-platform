from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "IndicTender Platform - CPPP Public Intelligence"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MongoDB connection
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "indic_tenders"
    
    # In-memory MongoDB compatibility fallback for frictionless local execution
    # when an external MongoDB daemon is not currently active
    AUTO_FALLBACK_MOCK_DB: bool = True

    # CPPP Public Portal Scraping Rules
    # Safe public access policy: No CAPTCHA bypassing, polite headers, rate limiting
    CPPP_BASE_URL: str = "https://eprocure.gov.in/eprocure/app"
    CPPP_ACTIVE_TENDERS_URL: str = "https://eprocure.gov.in/eprocure/app?page=FrontEndTendersByOrganisation&service=page"
    USER_AGENT: str = "IndicTenderPlatform/1.0 (+https://github.com/indic-tender/crawler; open-public-data-initiative)"
    SAFE_REQUEST_DELAY_SEC: float = 1.5
    SAFE_TIMEOUT_SEC: float = 15.0
    SAFE_MAX_RETRIES: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
