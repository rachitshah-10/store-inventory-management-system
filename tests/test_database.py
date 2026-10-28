"""Tests for database initialization, schema constraints, and seed data."""

import sqlite3
import pytest
from inventory_db import init_db
from seed_db import seed_database


def test_foreign_keys_enabled(db_conn: sqlite3.Connection) -> None:
    """Verify that foreign keys are enabled on the connection."""
    cursor = db_conn.execute("PRAGMA foreign_keys;")
    result = cursor.fetchone()
    assert result[0] == 1


def test_schema_rerun_idempotent(db_conn: sqlite3.Connection) -> None:
    """Verify running the schema a second time does not fail or erase data."""
    seed_database(db_conn)
    count_before = db_conn.execute("SELECT COUNT(*) FROM products;").fetchone()[0]

    # Run schema again
    init_db(db_conn)

    count_after = db_conn.execute("SELECT COUNT(*) FROM products;").fetchone()[0]
    assert count_before == count_after == 12


def test_negative_price_rejected(db_conn: sqlite3.Connection) -> None:
    """Verify that inserting a product with a negative price raises an IntegrityError."""
    # Insert supplier first
    db_conn.execute(
        "INSERT INTO suppliers (id, name, contact_email) VALUES (1, 'Test Sup', 'test@sup.com');"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            """
            INSERT INTO products (sku, name, category, supplier_id, unit_price, quantity_in_stock, reorder_level)
            VALUES ('TEST-SKU', 'Test Item', 'Tools', 1, -500, 10, 5);
            """
        )


def test_invalid_movement_reason_rejected(db_conn: sqlite3.Connection) -> None:
    """Verify that inserting a stock movement with an invalid reason is rejected."""
    seed_database(db_conn)
    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            """
            INSERT INTO stock_movements (product_id, change_amount, reason, created_at)
            VALUES (1, 5, 'damaged_goods', '2026-10-27 12:00:00');
            """
        )


def test_seed_database_counts(db_conn: sqlite3.Connection) -> None:
    """Verify seed data row counts and required distribution."""
    seed_database(db_conn)

    counts = {}
    for table in ["suppliers", "products", "sales", "sale_items", "stock_movements"]:
        cursor = db_conn.execute(f"SELECT COUNT(*) AS total FROM {table};")
        counts[table] = cursor.fetchone()["total"]

    assert counts["suppliers"] == 4
    assert counts["products"] == 12
    assert counts["sales"] == 5
    assert counts["sale_items"] == 12
    assert counts["stock_movements"] == 0

    # Verify at least 3 categories
    cat_cursor = db_conn.execute("SELECT COUNT(DISTINCT category) FROM products;")
    assert cat_cursor.fetchone()[0] >= 3

    # Verify at least 2 low stock products
    low_stock_cursor = db_conn.execute(
        "SELECT COUNT(*) FROM products WHERE quantity_in_stock <= reorder_level;"
    )
    assert low_stock_cursor.fetchone()[0] >= 2

    # Verify at least 2 products never sold
    never_sold_cursor = db_conn.execute(
        """
        SELECT COUNT(*) FROM products
        WHERE id NOT IN (SELECT DISTINCT product_id FROM sale_items);
        """
    )
    assert never_sold_cursor.fetchone()[0] >= 2
