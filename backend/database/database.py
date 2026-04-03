import os
import json
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


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma_async(dbapi_connection, connection_record):
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


def _run_schema_migrations():
    """
    Lightweight SQLite migrations for existing installs.
    """
    with sync_engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        migrations = []
        backfilled = 0

        if "accounts" in tables:
            account_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(accounts)").fetchall()
            }

            if "api_id" not in account_columns:
                migrations.append("ALTER TABLE accounts ADD COLUMN api_id INTEGER")
            if "api_hash" not in account_columns:
                migrations.append("ALTER TABLE accounts ADD COLUMN api_hash VARCHAR(64)")
            if "device_fingerprint" not in account_columns:
                migrations.append("ALTER TABLE accounts ADD COLUMN device_fingerprint TEXT")
            if "fingerprint_locked_at" not in account_columns:
                migrations.append("ALTER TABLE accounts ADD COLUMN fingerprint_locked_at DATETIME")
            if "last_check_error_code" not in account_columns:
                migrations.append("ALTER TABLE accounts ADD COLUMN last_check_error_code VARCHAR(64)")
            if "last_check_error" not in account_columns:
                migrations.append("ALTER TABLE accounts ADD COLUMN last_check_error TEXT")
            if "is_premium" not in account_columns:
                migrations.append("ALTER TABLE accounts ADD COLUMN is_premium BOOLEAN DEFAULT 0")

            for migration in migrations:
                conn.exec_driver_sql(migration)

            # Backfill API/device metadata for legacy imports that stored data only in extra_data.
            if "extra_data" in account_columns:
                from telegram.account_metadata import (
                    extract_api_credentials,
                    merge_device_fingerprint,
                    normalize_device_fingerprint,
                    normalize_json_dict,
                )

                rows = conn.exec_driver_sql(
                    "SELECT id, api_id, api_hash, device_fingerprint, extra_data FROM accounts"
                ).fetchall()

                for account_id, api_id, api_hash, device_fingerprint, extra_data in rows:
                    extra_dict = normalize_json_dict(extra_data)
                    if not extra_dict:
                        continue

                    new_api_id = api_id
                    new_api_hash = api_hash

                    if new_api_id is None or not new_api_hash:
                        extra_api_id, extra_api_hash = extract_api_credentials(extra_dict)
                        if new_api_id is None:
                            new_api_id = extra_api_id
                        if not new_api_hash:
                            new_api_hash = extra_api_hash

                    current_fp = normalize_device_fingerprint(device_fingerprint)
                    merged_fp = merge_device_fingerprint(device_fingerprint, extra_dict)

                    fp_changed = merged_fp != current_fp and bool(merged_fp)
                    api_changed = (new_api_id != api_id) or (new_api_hash != api_hash)

                    if not fp_changed and not api_changed:
                        continue

                    conn.exec_driver_sql(
                        "UPDATE accounts SET api_id = ?, api_hash = ?, device_fingerprint = ? WHERE id = ?",
                        (
                            new_api_id,
                            new_api_hash,
                            json.dumps(merged_fp, ensure_ascii=False) if merged_fp else device_fingerprint,
                            account_id,
                        ),
                    )
                    backfilled += 1

        if "comment_templates" in tables:
            template_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(comment_templates)").fetchall()
            }

            if "category" not in template_columns:
                conn.exec_driver_sql(
                    "ALTER TABLE comment_templates ADD COLUMN category VARCHAR(100) DEFAULT 'General'"
                )
                migrations.append("ALTER TABLE comment_templates ADD COLUMN category VARCHAR(100) DEFAULT 'General'")

            conn.exec_driver_sql(
                "UPDATE comment_templates SET category = 'General' "
                "WHERE category IS NULL OR TRIM(category) = ''"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_comment_templates_category "
                "ON comment_templates (category)"
            )

        if migrations:
            print(f"[Backend] Applied {len(migrations)} schema migration(s)")
        if backfilled:
            print(f"[Backend] Backfilled metadata for {backfilled} account(s)")


async def init_db():
    """Initialize database and create tables"""
    from database.models import (
        Account,
        Proxy,
        AccountGroup,
        AccountTag,
        Task,
        TaskLog,
        CommentTemplate,
        TargetChannel,
        SavedChannel,
        ChannelMembership,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Also create tables for sync engine
    Base.metadata.create_all(bind=sync_engine)
    _run_schema_migrations()


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
