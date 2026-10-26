from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import settings
from app.db.connection import get_db_status

router = APIRouter(prefix="/api", tags=["System Health"])
_start_time = datetime.now(timezone.utc)


@router.get("/health", summary="System health and database status")
def get_health():
    db_status = get_db_status()
    uptime_sec = round((datetime.now(timezone.utc) - _start_time).total_seconds(), 2)
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "uptime_seconds": uptime_sec,
        "database": db_status,
        "safe_crawler_policy": {
            "rate_limit_delay_sec": settings.SAFE_REQUEST_DELAY_SEC,
            "captcha_bypass_allowed": False,
            "authentication_required": False,
            "user_agent": settings.USER_AGENT
        }
    }
