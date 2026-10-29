"""Database connection, queries, and product management operations."""

import os
import sqlite3
from pathlib import Path


class InventoryError(Exception):
    """Base exception for inventory operations."""


class DuplicateSkuError(InventoryError):
    """Raised when adding a product with a SKU that already exists."""


class UnknownSupplierError(InventoryError):
    """Raised when referencing a supplier ID that is not in the suppliers table."""


class InvalidProductDataError(InventoryError):
    """Raised when price, quantity, or reorder level values are negative."""


class ProductHasSalesHistoryError(InventoryError):
    """Raised when attempting to delete a product that appears in sales history."""


def get_default_db_path() -> str:
    """Return the database file path from environment variable or local fallback."""
    env_path = os.environ.get("INVENTORY_DB")
    if env_path:
        return env_path
    return str(Path(__file__).resolve().parent / "inventory.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Create and return a database connection with foreign keys enabled."""
    if db_path is None:
        db_path = get_default_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection, schema_path: str | Path | None = None) -> None:
    """Run the schema.sql script to set up all tables and indexes if they do not exist."""
    if schema_path is None:
        schema_path = Path(__file__).resolve().parent / "schema.sql"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn.executescript(schema_sql)


def add_product(
    conn: sqlite3.Connection,
    sku: str,
    name: str,
    category: str,
    supplier_id: int,
    unit_price: int,
    quantity_in_stock: int,
    reorder_level: int,
) -> int:
    """Add a new product to the database and return its new integer ID."""
    if unit_price < 0 or quantity_in_stock < 0 or reorder_level < 0:
        raise InvalidProductDataError("Price, quantity, and reorder level cannot be negative.")

    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO products (
                    sku, name, category, supplier_id, unit_price, quantity_in_stock, reorder_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (sku, name, category, supplier_id, unit_price, quantity_in_stock, reorder_level),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        err = str(exc).lower()
        if "unique" in err and "sku" in err:
            raise DuplicateSkuError(f"A product with SKU '{sku}' already exists.") from exc
        if "foreign key" in err:
            raise UnknownSupplierError(f"Supplier ID {supplier_id} does not exist.") from exc
        if "check" in err:
            raise InvalidProductDataError("Database check constraint failed on product values.") from exc
        raise


def get_product(conn: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    """Look up a single product by ID, joined with its supplier to get the supplier name."""
    cursor = conn.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, p.supplier_id,
               s.name AS supplier_name,
               p.unit_price, p.quantity_in_stock, p.reorder_level
        FROM products p
        JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.id = ?;
        """,
        (product_id,),
    )
    return cursor.fetchone()


def update_price(conn: sqlite3.Connection, product_id: int, new_price: int) -> bool:
    """Update a product's unit price in whole cents. Returns True if updated, False if missing."""
    if new_price < 0:
        raise InvalidProductDataError("Unit price cannot be negative.")

    with conn:
        cursor = conn.execute(
            "UPDATE products SET unit_price = ? WHERE id = ?;",
            (new_price, product_id),
        )
        return cursor.rowcount > 0


def delete_product(conn: sqlite3.Connection, product_id: int) -> bool:
    """Delete a product by ID if it has never been sold.

    Raises ProductHasSalesHistoryError if the product appears in sale_items.
    Returns True if deleted, False if the product does not exist.
    """
    # Check whether the product has any recorded sales
    sales_check = conn.execute(
        "SELECT 1 FROM sale_items WHERE product_id = ? LIMIT 1;",
        (product_id,),
    ).fetchone()
    if sales_check:
        raise ProductHasSalesHistoryError(
            f"Product ID {product_id} cannot be deleted because it has recorded sales."
        )

    try:
        with conn:
            cursor = conn.execute("DELETE FROM products WHERE id = ?;", (product_id,))
            return cursor.rowcount > 0
    except sqlite3.IntegrityError as exc:
        # Enforce database-level foreign key restriction as well
        raise ProductHasSalesHistoryError(
            f"Product ID {product_id} cannot be deleted due to existing database references."
        ) from exc


def search_products(
    conn: sqlite3.Connection,
    text: str | None = None,
    category: str | None = None,
    max_price: int | None = None,
    in_stock_only: bool = False,
    low_stock_only: bool = False,
) -> list[sqlite3.Row]:
    """Search for products using case-insensitive text matching and optional filters."""
    query = """
        SELECT p.id, p.sku, p.name, p.category, p.supplier_id,
               s.name AS supplier_name,
               p.unit_price, p.quantity_in_stock, p.reorder_level
        FROM products p
        JOIN suppliers s ON p.supplier_id = s.id
    """
    conditions: list[str] = []
    params: list[object] = []

    if text:
        conditions.append(
            "(p.name LIKE ? COLLATE NOCASE OR p.sku LIKE ? COLLATE NOCASE OR s.name LIKE ? COLLATE NOCASE)"
        )
        search_pattern = f"%{text}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    if category:
        conditions.append("p.category = ? COLLATE NOCASE")
        params.append(category)

    if max_price is not None:
        conditions.append("p.unit_price <= ?")
        params.append(max_price)

    if in_stock_only:
        conditions.append("p.quantity_in_stock > 0")

    if low_stock_only:
        conditions.append("p.quantity_in_stock <= p.reorder_level")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY p.name ASC;"

    cursor = conn.execute(query, params)
    return cursor.fetchall()
