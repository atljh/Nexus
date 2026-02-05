"""
Migration: Add api_id, api_hash, device_fingerprint to accounts table.

Run this script once to add the new columns to existing database.
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

    migrations = []

    # Add api_id column
    if "api_id" not in existing_columns:
        migrations.append("ALTER TABLE accounts ADD COLUMN api_id INTEGER")

    # Add api_hash column
    if "api_hash" not in existing_columns:
        migrations.append("ALTER TABLE accounts ADD COLUMN api_hash VARCHAR(64)")

    # Add device_fingerprint column (JSON stored as TEXT in SQLite)
    if "device_fingerprint" not in existing_columns:
        migrations.append("ALTER TABLE accounts ADD COLUMN device_fingerprint TEXT")

    if not migrations:
        print("No migrations needed, all columns exist")
        return

    for migration in migrations:
        print(f"Running: {migration}")
        cursor.execute(migration)

    conn.commit()
    conn.close()

    print(f"Migration completed. Added {len(migrations)} columns.")


if __name__ == "__main__":
    migrate()
