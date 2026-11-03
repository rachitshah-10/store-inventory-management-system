"""Tests for database backup and restore functionality."""

from pathlib import Path
import sqlite3
from inventory_db import backup_database, connect, restore_database
from seed_db import seed_database


def test_backup_integrity_and_row_counts(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """A backup passes the integrity check and has the same row counts."""
    seed_database(db_conn)

    backup_file = tmp_path / "inventory_backup.db"
    backup_database(db_conn, backup_file)

    assert backup_file.exists()

    # Open the backup database and verify integrity
    backup_conn = connect(str(backup_file))
    try:
        integrity_row = backup_conn.execute("PRAGMA integrity_check;").fetchone()
        assert integrity_row[0] == "ok"

        # Verify all table row counts match the original
        tables = ["suppliers", "products", "sales", "sale_items", "stock_movements"]
        for table in tables:
            orig_count = db_conn.execute(
                f"SELECT COUNT(*) FROM {table};"
            ).fetchone()[0]
            backup_count = backup_conn.execute(
                f"SELECT COUNT(*) FROM {table};"
            ).fetchone()[0]
            assert backup_count == orig_count
    finally:
        backup_conn.close()


def test_restore_database(db_conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Verifies that a restored database recovers all records into a target database."""
    seed_database(db_conn)

    backup_file = tmp_path / "restore_test.db"
    backup_database(db_conn, backup_file)

    # Create a fresh empty in-memory database and restore from the backup
    new_conn = connect(":memory:")
    try:
        restore_database(backup_file, new_conn)

        integrity = new_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        assert integrity == "ok"

        count = new_conn.execute("SELECT COUNT(*) FROM products;").fetchone()[0]
        assert count == 12
    finally:
        new_conn.close()

