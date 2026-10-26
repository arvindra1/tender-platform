import logging
from typing import Any, Dict
import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import mongomock
from app.config import settings

logger = logging.getLogger("indic_tender.db")

_sync_client = None
_sync_db = None
_is_mock_mode = False


class AsyncMockCollection:
    """Async wrapper around mongomock collection for async/await route parity."""
    def __init__(self, sync_collection):
        self._coll = sync_collection

    def __getattr__(self, name):
        attr = getattr(self._coll, name)
        if callable(attr):
            async def async_wrapper(*args, **kwargs):
                result = attr(*args, **kwargs)
                # If result is a cursor, convert to list or mock cursor
                if hasattr(result, "to_list"):
                    return result
                return result
            return async_wrapper
        return attr

    async def find_one(self, *args, **kwargs):
        return self._coll.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._coll.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._coll.update_one(*args, **kwargs)

    async def replace_one(self, *args, **kwargs):
        return self._coll.replace_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._coll.delete_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._coll.count_documents(*args, **kwargs)

    async def create_index(self, *args, **kwargs):
        return self._coll.create_index(*args, **kwargs)

    async def distinct(self, *args, **kwargs):
        return self._coll.distinct(*args, **kwargs)

    def find(self, *args, **kwargs):
        cursor = self._coll.find(*args, **kwargs)
        return AsyncMockCursor(cursor)

    def aggregate(self, *args, **kwargs):
        cursor = self._coll.aggregate(*args, **kwargs)
        return AsyncMockCursor(cursor)


class AsyncMockCursor:
    """Async cursor wrapper for mongomock."""
    def __init__(self, sync_cursor):
        self._cursor = sync_cursor

    def sort(self, *args, **kwargs):
        self._cursor.sort(*args, **kwargs)
        return self

    def skip(self, count: int):
        self._cursor.skip(count)
        return self

    def limit(self, count: int):
        self._cursor.limit(count)
        return self

    async def to_list(self, length: int = None):
        if length is not None:
            items = []
            for item in self._cursor:
                items.append(item)
                if len(items) >= length:
                    break
            return items
        return list(self._cursor)

    def __aiter__(self):
        self._iter = iter(self._cursor)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class AsyncMockDatabase:
    """Async database wrapper for mongomock."""
    def __init__(self, sync_db):
        self._db = sync_db

    def __getitem__(self, name: str):
        return AsyncMockCollection(self._db[name])

    def get_collection(self, name: str):
        return AsyncMockCollection(self._db[name])

    async def list_collection_names(self):
        return self._db.list_collection_names()


def init_db():
    """Initialize DB connection with automatic fallback to mock memory DB if MongoDB is offline."""
    global _sync_client, _sync_db, _is_mock_mode
    if _sync_db is not None:
        return _sync_db

    try:
        # Test real MongoDB connection with short timeout
        logger.info(f"Connecting to MongoDB at {settings.MONGO_URI}...")
        client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=1500,
            connectTimeoutMS=1500
        )
        client.admin.command("ping")
        _sync_client = client
        _sync_db = client[settings.DB_NAME]
        _is_mock_mode = False
        logger.info(f"Successfully connected to active MongoDB database '{settings.DB_NAME}'")
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as exc:
        if settings.AUTO_FALLBACK_MOCK_DB:
            logger.warning(
                f"External MongoDB daemon not detected at {settings.MONGO_URI} ({exc}). "
                "Activating high-fidelity In-Memory MongoDB compatibility engine for frictionless local runtime."
            )
            _sync_client = mongomock.MongoClient()
            _sync_db = _sync_client[settings.DB_NAME]
            _is_mock_mode = True
        else:
            logger.error(f"Failed to connect to MongoDB: {exc}")
            raise exc

    return _sync_db


def get_sync_db():
    if _sync_db is None:
        init_db()
    return _sync_db


def get_async_db():
    """Return database handle. If mock mode, returns async-compatible wrapper."""
    db = get_sync_db()
    if _is_mock_mode:
        return AsyncMockDatabase(db)
    
    # Motor client for real MongoDB
    from motor.motor_asyncio import AsyncIOMotorClient
    motor_client = AsyncIOMotorClient(settings.MONGO_URI)
    return motor_client[settings.DB_NAME]


def get_db_status() -> Dict[str, Any]:
    db = get_sync_db()
    return {
        "status": "healthy",
        "mode": "in_memory_compatibility" if _is_mock_mode else "mongodb_cluster",
        "database": settings.DB_NAME,
        "uri": "in-memory-mock" if _is_mock_mode else settings.MONGO_URI,
        "is_mock": _is_mock_mode
    }
