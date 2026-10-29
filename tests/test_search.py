"""Tests for search operations matching the assignment test plan."""

import sqlite3
import pytest
from inventory_db import search_products
from seed_db import seed_database


@pytest.mark.parametrize(
    ("query_text", "expected_sku"),
    [
        ("claw hammer", "TOOL-HAM-01"),  # matches name ignoring case
        ("DRYW-01", "SCRW-DRYW-01"),     # matches SKU ignoring case
        ("apex tool", "TOOL-HAM-01"),    # matches supplier name ignoring case
    ],
)
def test_search_matches_ignoring_case(
    db_conn: sqlite3.Connection, query_text: str, expected_sku: str
) -> None:
    """Search matches name, SKU, and supplier name ignoring case (parametrized)."""
    seed_database(db_conn)
    results = search_products(db_conn, text=query_text)
    skus = [r["sku"] for r in results]
    assert expected_sku in skus


def test_search_filters_work(db_conn: sqlite3.Connection) -> None:
    """Each individual search filter works."""
    seed_database(db_conn)

    # Category filter
    tools = search_products(db_conn, category="Tools")
    assert all(r["category"] == "Tools" for r in tools)

    # Max price filter ($10.00 = 1000 cents)
    cheap = search_products(db_conn, max_price=1000)
    assert all(r["unit_price"] <= 1000 for r in cheap)

    # In stock only filter
    db_conn.execute("UPDATE products SET quantity_in_stock = 0 WHERE id = 1;")
    in_stock = search_products(db_conn, in_stock_only=True)
    assert all(r["quantity_in_stock"] > 0 for r in in_stock)

    # Low stock only filter
    low_stock = search_products(db_conn, low_stock_only=True)
    assert all(r["quantity_in_stock"] <= r["reorder_level"] for r in low_stock)


def test_search_filters_combine(db_conn: sqlite3.Connection) -> None:
    """Filters can be combined together."""
    seed_database(db_conn)
    results = search_products(
        db_conn,
        text="paint",
        category="Paint",
        max_price=1500,
        in_stock_only=True,
    )
    for item in results:
        assert item["category"] == "Paint"
        assert item["unit_price"] <= 1500
        assert item["quantity_in_stock"] > 0


def test_search_dangerous_text_safe(db_conn: sqlite3.Connection) -> None:
    """Dangerous looking text never runs as SQL."""
    seed_database(db_conn)
    payload = "'; DROP TABLE products; --"
    results = search_products(db_conn, text=payload)
    assert len(results) == 0

    # Verify table remains intact
    count = db_conn.execute("SELECT COUNT(*) FROM products;").fetchone()[0]
    assert count == 12
