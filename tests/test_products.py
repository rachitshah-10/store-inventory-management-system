"""Tests for product operations matching the assignment test plan."""

import sqlite3
import pytest
from inventory_db import (
    DuplicateSkuError,
    InvalidProductDataError,
    ProductHasSalesHistoryError,
    UnknownSupplierError,
    add_product,
    delete_product,
    get_product,
    update_price,
)
from seed_db import seed_database


def test_add_product_returns_new_id(db_conn: sqlite3.Connection) -> None:
    """Adding a product returns its new id."""
    seed_database(db_conn)
    new_id = add_product(
        db_conn,
        sku="TEST-SKU-99",
        name="Tape Measure 25ft",
        category="Tools",
        supplier_id=2,
        unit_price=1250,
        quantity_in_stock=20,
        reorder_level=5,
    )
    assert isinstance(new_id, int)
    assert new_id > 0


def test_add_product_duplicate_sku_refused(db_conn: sqlite3.Connection) -> None:
    """Duplicate SKU is refused."""
    seed_database(db_conn)
    with pytest.raises(DuplicateSkuError):
        add_product(
            db_conn,
            sku="SCRW-WOOD-01",  # exists in seed data
            name="Another Screw",
            category="Hardware",
            supplier_id=1,
            unit_price=999,
            quantity_in_stock=10,
            reorder_level=5,
        )


def test_add_product_unknown_supplier_refused(db_conn: sqlite3.Connection) -> None:
    """Unknown supplier is refused."""
    seed_database(db_conn)
    with pytest.raises(UnknownSupplierError):
        add_product(
            db_conn,
            sku="NEW-ITEM-01",
            name="Mystery Item",
            category="Hardware",
            supplier_id=9999,
            unit_price=500,
            quantity_in_stock=10,
            reorder_level=5,
        )


@pytest.mark.parametrize(
    ("price", "qty"),
    [
        (-100, 10),  # negative price
        (500, -5),   # negative quantity
    ],
)
def test_add_product_negative_price_or_quantity_refused(
    db_conn: sqlite3.Connection, price: int, qty: int
) -> None:
    """Negative price or quantity are each refused (parametrized)."""
    seed_database(db_conn)
    with pytest.raises(InvalidProductDataError):
        add_product(
            db_conn,
            sku="INVALID-NUMS",
            name="Invalid Product",
            category="Hardware",
            supplier_id=1,
            unit_price=price,
            quantity_in_stock=qty,
            reorder_level=5,
        )


def test_update_price_works(db_conn: sqlite3.Connection) -> None:
    """Changing a price works."""
    seed_database(db_conn)
    assert update_price(db_conn, product_id=1, new_price=999) is True
    assert get_product(db_conn, 1)["unit_price"] == 999


def test_update_price_missing_product_returns_false(db_conn: sqlite3.Connection) -> None:
    """Changing a missing product returns false."""
    seed_database(db_conn)
    assert update_price(db_conn, product_id=9999, new_price=500) is False


def test_delete_product_sold_refused(db_conn: sqlite3.Connection) -> None:
    """A sold product cannot be deleted."""
    seed_database(db_conn)
    with pytest.raises(ProductHasSalesHistoryError):
        delete_product(db_conn, product_id=1)


def test_delete_product_never_sold_success(db_conn: sqlite3.Connection) -> None:
    """A never sold product can be deleted."""
    seed_database(db_conn)
    assert delete_product(db_conn, product_id=8) is True
    assert get_product(db_conn, 8) is None
