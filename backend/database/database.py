import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

# Database path (overrideable for tests/CI)
_db_path_env = os.getenv("NEXUS_DB_PATH")
if _db_path_env:
    DB_PATH = Path(_db_path_env).expanduser()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    DB_DIR = Path.home() / "Nexus"
    DB_DIR.mkdir(exist_ok=True)
    DB_PATH = DB_DIR / "nexus.db"

# Async database URL (for FastAPI endpoints)
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Sync database URL (for workers)
SYNC_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Async engine and session (for API)
engine = create_async_engine(DATABASE_URL, echo=False)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Sync engine and session (for workers)
sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)


# Enable SQLite foreign keys for both engines
@event.listens_for(sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Initialize database and create tables"""
    from database.models import Account, Proxy, AccountGroup, AccountTag, Task, TaskLog, CommentTemplate, TargetChannel

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Also create tables for sync engine
    Base.metadata.create_all(bind=sync_engine)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


def get_db():
    """Dependency for sync database session (used in API endpoints)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
