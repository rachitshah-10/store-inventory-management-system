"""Tests for inventory and sales reporting matching the assignment test plan."""

import sqlite3
from inventory_db import (
    format_cents,
    report_low_stock,
    report_never_sold,
    report_sales_by_product,
    report_stock_value_by_supplier,
)
from seed_db import seed_database


def test_report_stock_value_by_supplier(db_conn: sqlite3.Connection) -> None:
    """Verify stock value report returns suppliers ordered by total value descending."""
    seed_database(db_conn)
    rows = report_stock_value_by_supplier(db_conn)
    assert len(rows) == 4

    # Verify highest first order
    values = [r["total_value"] for r in rows]
    assert values == sorted(values, reverse=True)

    # Check top supplier matching sample data
    assert rows[0]["supplier_name"] == "Bright Paints & Finishes"
    assert rows[0]["total_value"] == 171986
    assert format_cents(rows[0]["total_value"]) == "$1719.86"


def test_report_low_stock(db_conn: sqlite3.Connection) -> None:
    """Verify low stock report returns products at or below reorder level with units short."""
    seed_database(db_conn)
    rows = report_low_stock(db_conn)
    assert len(rows) == 2

    # In seed data: Drywall Screws (8 in stock, reorder 15 -> 7 short)
    # Hex Bolts (5 in stock, reorder 10 -> 5 short)
    skus = [r["sku"] for r in rows]
    assert "SCRW-DRYW-01" in skus
    assert "BOLT-HEX-01" in skus

    for r in rows:
        assert r["units_short"] == r["reorder_level"] - r["quantity_in_stock"]
        assert r["units_short"] > 0


def test_report_sales_by_product(db_conn: sqlite3.Connection) -> None:
    """Verify sales by product report returns units sold and revenue, highest revenue first."""
    seed_database(db_conn)
    rows = report_sales_by_product(db_conn)
    assert len(rows) == 10

    # Verify highest revenue first
    revenues = [r["total_revenue"] for r in rows]
    assert revenues == sorted(revenues, reverse=True)

    # Top product by revenue in sample data is White Primer (2 @ 3200 = 6400)
    assert rows[0]["name"] == "White Primer 1gal"
    assert rows[0]["units_sold"] == 2
    assert rows[0]["total_revenue"] == 6400


def test_report_never_sold(db_conn: sqlite3.Connection) -> None:
    """Verify never sold report returns products that appear in no sales."""
    seed_database(db_conn)
    rows = report_never_sold(db_conn)
    assert len(rows) == 2

    skus = sorted([r["sku"] for r in rows])
    assert skus == ["PNT-TRP-01", "TOOL-LEV-01"]

