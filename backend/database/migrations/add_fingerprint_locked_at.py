"""
Migration: Add fingerprint_locked_at to accounts table.

Run this script once to add the new column to existing database.
"""
import sqlite3
from pathlib import Path


def migrate():
    db_path = Path.home() / "Nexus" / "nexus.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}, skipping migration")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(accounts)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "fingerprint_locked_at" in existing_columns:
        print("No migration needed, fingerprint_locked_at column already exists")
        conn.close()
        return

    migration = "ALTER TABLE accounts ADD COLUMN fingerprint_locked_at DATETIME"
    print(f"Running: {migration}")
    cursor.execute(migration)

    conn.commit()
    conn.close()

    print("Migration completed. Added fingerprint_locked_at column.")


if __name__ == "__main__":
    migrate()
