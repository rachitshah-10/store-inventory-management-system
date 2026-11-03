"""Tests for stock restock, adjustments, and sales transactions."""

import sqlite3
import pytest
from inventory_db import (
    InsufficientStockError,
    InvalidStockChangeError,
    ProductNotFoundError,
    adjust,
    get_product,
    record_sale,
    restock,
)
from seed_db import seed_database


def test_restock_increases_stock_and_logs_movement(db_conn: sqlite3.Connection) -> None:
    """A restock increases stock and logs one movement, and a restock of zero or less is refused."""
    seed_database(db_conn)

    initial_stock = get_product(db_conn, 1)["quantity_in_stock"]
    test_time = "2026-11-03 10:00:00"

    movement_id = restock(db_conn, product_id=1, amount=15, timestamp=test_time)
    assert movement_id > 0

    # Verify stock increased
    updated = get_product(db_conn, 1)
    assert updated["quantity_in_stock"] == initial_stock + 15

    # Verify movement log entry
    movement = db_conn.execute(
        "SELECT * FROM stock_movements WHERE id = ?;", (movement_id,)
    ).fetchone()
    assert movement["product_id"] == 1
    assert movement["change_amount"] == 15
    assert movement["reason"] == "restock"
    assert movement["created_at"] == test_time

    # Verify restock of 0 or negative is refused
    with pytest.raises(InvalidStockChangeError):
        restock(db_conn, product_id=1, amount=0)

    with pytest.raises(InvalidStockChangeError):
        restock(db_conn, product_id=1, amount=-5)


def test_adjustment_cannot_make_stock_negative(db_conn: sqlite3.Connection) -> None:
    """An adjustment cannot make stock negative, and a refused adjustment changes nothing."""
    seed_database(db_conn)

    # Product 2 has 8 in stock in seed data
    initial_stock = get_product(db_conn, 2)["quantity_in_stock"]
    initial_movements = db_conn.execute("SELECT COUNT(*) FROM stock_movements;").fetchone()[0]

    # Valid negative adjustment (damage/loss)
    adjust(db_conn, product_id=2, change_amount=-3, timestamp="2026-11-03 10:15:00")
    assert get_product(db_conn, 2)["quantity_in_stock"] == initial_stock - 3

    # Attempt an adjustment that drops stock below zero (current stock is 5)
    with pytest.raises(InsufficientStockError):
        adjust(db_conn, product_id=2, change_amount=-10)

    # Verify stock remained at 5 and no extra movement was logged for the failed adjustment
    assert get_product(db_conn, 2)["quantity_in_stock"] == 5
    current_movements = db_conn.execute("SELECT COUNT(*) FROM stock_movements;").fetchone()[0]
    assert current_movements == initial_movements + 1


def test_sale_records_lines_stock_and_movements(db_conn: sqlite3.Connection) -> None:
    """A sale records its lines at current prices, reduces stock, and logs a movement for each line."""
    seed_database(db_conn)

    # Product 1 ($8.99 = 899 cents, stock 50) and Product 5 ($19.99 = 1999 cents, stock 25)
    sale_time = "2026-11-03 11:30:00"
    items_to_buy = [(1, 3), (5, 2)]

    sale_id = record_sale(db_conn, items_to_buy, timestamp=sale_time)
    assert sale_id > 0

    # Verify line items recorded at current product prices
    lines = db_conn.execute(
        "SELECT * FROM sale_items WHERE sale_id = ? ORDER BY product_id ASC;",
        (sale_id,),
    ).fetchall()
    assert len(lines) == 2
    assert lines[0]["product_id"] == 1
    assert lines[0]["quantity"] == 3
    assert lines[0]["price_at_sale"] == 899
    assert lines[1]["product_id"] == 5
    assert lines[1]["quantity"] == 2
    assert lines[1]["price_at_sale"] == 1999

    # Verify stock levels reduced
    assert get_product(db_conn, 1)["quantity_in_stock"] == 50 - 3
    assert get_product(db_conn, 5)["quantity_in_stock"] == 25 - 2

    # Verify movements logged for each line
    movements = db_conn.execute(
        "SELECT * FROM stock_movements WHERE created_at = ? ORDER BY product_id ASC;",
        (sale_time,),
    ).fetchall()
    assert len(movements) == 2
    assert movements[0]["product_id"] == 1
    assert movements[0]["change_amount"] == -3
    assert movements[0]["reason"] == "sale"
    assert movements[1]["product_id"] == 5
    assert movements[1]["change_amount"] == -2
    assert movements[1]["reason"] == "sale"


def test_sale_fails_halfway_changes_nothing(db_conn: sqlite3.Connection) -> None:
    """A sale that fails halfway changes nothing: no sale row, no lines, no movements, and no stock change."""
    seed_database(db_conn)

    # Record baseline state before attempt
    sales_before = db_conn.execute("SELECT COUNT(*) FROM sales;").fetchone()[0]
    items_before = db_conn.execute("SELECT COUNT(*) FROM sale_items;").fetchone()[0]
    movements_before = db_conn.execute("SELECT COUNT(*) FROM stock_movements;").fetchone()[0]
    prod1_stock_before = get_product(db_conn, 1)["quantity_in_stock"]
    prod2_stock_before = get_product(db_conn, 2)["quantity_in_stock"]

    # Product 1 has 50 in stock (valid), but Product 2 only has 8 (requesting 50 fails)
    failing_sale = [(1, 2), (2, 50)]

    with pytest.raises(InsufficientStockError):
        record_sale(db_conn, failing_sale)

    # Verify that the entire transaction rolled back with zero side effects
    assert db_conn.execute("SELECT COUNT(*) FROM sales;").fetchone()[0] == sales_before
    assert db_conn.execute("SELECT COUNT(*) FROM sale_items;").fetchone()[0] == items_before
    assert db_conn.execute("SELECT COUNT(*) FROM stock_movements;").fetchone()[0] == movements_before
    assert get_product(db_conn, 1)["quantity_in_stock"] == prod1_stock_before
    assert get_product(db_conn, 2)["quantity_in_stock"] == prod2_stock_before


def test_sale_for_unknown_product_changes_nothing(db_conn: sqlite3.Connection) -> None:
    """A sale for an unknown product changes nothing."""
    seed_database(db_conn)

    sales_before = db_conn.execute("SELECT COUNT(*) FROM sales;").fetchone()[0]
    items_before = db_conn.execute("SELECT COUNT(*) FROM sale_items;").fetchone()[0]
    prod1_stock_before = get_product(db_conn, 1)["quantity_in_stock"]

    with pytest.raises(ProductNotFoundError):
        record_sale(db_conn, [(1, 1), (9999, 1)])

    assert db_conn.execute("SELECT COUNT(*) FROM sales;").fetchone()[0] == sales_before
    assert db_conn.execute("SELECT COUNT(*) FROM sale_items;").fetchone()[0] == items_before
    assert get_product(db_conn, 1)["quantity_in_stock"] == prod1_stock_before

