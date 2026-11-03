"""Database connection, queries, and product management operations."""

import os
import sqlite3
from datetime import datetime
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


class InvalidStockChangeError(InventoryError):
    """Raised when restock or adjustment amounts are invalid."""


class InsufficientStockError(InventoryError):
    """Raised when an adjustment or sale would reduce stock below zero."""


class ProductNotFoundError(InventoryError):
    """Raised when an operation references a product that does not exist."""


class DuplicateSaleItemError(InventoryError):
    """Raised when a single sale attempts to include the same product multiple times."""


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


def format_cents(cents: int) -> str:
    """Format an integer amount of cents as a standard currency string (e.g. 1050 -> '$10.50')."""
    return f"${cents / 100:.2f}"


def report_stock_value_by_supplier(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Calculate the total inventory value for each supplier, sorted highest value first."""
    cursor = conn.execute(
        """
        SELECT s.name AS supplier_name,
               COALESCE(SUM(p.unit_price * p.quantity_in_stock), 0) AS total_value
        FROM suppliers s
        LEFT JOIN products p ON s.id = p.supplier_id
        GROUP BY s.id, s.name
        ORDER BY total_value DESC, s.name ASC;
        """
    )
    return cursor.fetchall()


def report_low_stock(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all products at or below their reorder level with the units short."""
    cursor = conn.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, p.quantity_in_stock, p.reorder_level,
               (p.reorder_level - p.quantity_in_stock) AS units_short
        FROM products p
        WHERE p.quantity_in_stock <= p.reorder_level
        ORDER BY units_short DESC, p.name ASC;
        """
    )
    return cursor.fetchall()


def report_sales_by_product(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return total units sold and total revenue for each sold product, highest revenue first."""
    cursor = conn.execute(
        """
        SELECT p.id, p.sku, p.name,
               SUM(si.quantity) AS units_sold,
               SUM(si.quantity * si.price_at_sale) AS total_revenue
        FROM products p
        JOIN sale_items si ON p.id = si.product_id
        GROUP BY p.id, p.sku, p.name
        ORDER BY total_revenue DESC, p.name ASC;
        """
    )
    return cursor.fetchall()


def report_never_sold(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all products that have never appeared in any sale record."""
    cursor = conn.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, p.unit_price, p.quantity_in_stock
        FROM products p
        LEFT JOIN sale_items si ON p.id = si.product_id
        WHERE si.id IS NULL
        ORDER BY p.name ASC;
        """
    )
    return cursor.fetchall()


def restock(
    conn: sqlite3.Connection,
    product_id: int,
    amount: int,
    timestamp: str | None = None,
) -> int:
    """Add incoming stock for a product and log the movement in a single transaction."""
    if amount <= 0:
        raise InvalidStockChangeError("Restock amount must be greater than zero.")

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn:
        prod = conn.execute(
            "SELECT id, quantity_in_stock FROM products WHERE id = ?;",
            (product_id,),
        ).fetchone()
        if prod is None:
            raise ProductNotFoundError(f"Product ID {product_id} does not exist.")

        conn.execute(
            "UPDATE products SET quantity_in_stock = quantity_in_stock + ? WHERE id = ?;",
            (amount, product_id),
        )
        cursor = conn.execute(
            """
            INSERT INTO stock_movements (product_id, change_amount, reason, created_at)
            VALUES (?, ?, 'restock', ?);
            """,
            (product_id, amount, timestamp),
        )
        return cursor.lastrowid


def adjust(
    conn: sqlite3.Connection,
    product_id: int,
    change_amount: int,
    timestamp: str | None = None,
) -> int:
    """Adjust stock for recount or damage and log the movement in a single transaction."""
    if change_amount == 0:
        raise InvalidStockChangeError("Adjustment amount cannot be zero.")

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn:
        prod = conn.execute(
            "SELECT id, quantity_in_stock FROM products WHERE id = ?;",
            (product_id,),
        ).fetchone()
        if prod is None:
            raise ProductNotFoundError(f"Product ID {product_id} does not exist.")

        new_stock = prod["quantity_in_stock"] + change_amount
        if new_stock < 0:
            raise InsufficientStockError(
                f"Adjustment of {change_amount} would reduce stock below zero (current: {prod['quantity_in_stock']})."
            )

        conn.execute(
            "UPDATE products SET quantity_in_stock = ? WHERE id = ?;",
            (new_stock, product_id),
        )
        cursor = conn.execute(
            """
            INSERT INTO stock_movements (product_id, change_amount, reason, created_at)
            VALUES (?, ?, 'adjustment', ?);
            """,
            (product_id, change_amount, timestamp),
        )
        return cursor.lastrowid


def record_sale(
    conn: sqlite3.Connection,
    items: list[tuple[int, int]],
    timestamp: str | None = None,
) -> int:
    """Record a multi-item sale, deduct inventory, and log movements atomically."""
    if not items:
        raise InvalidStockChangeError("A sale must include at least one item.")

    # Guard against listing the same product twice in the same sale
    seen_products = set()
    for product_id, quantity in items:
        if product_id in seen_products:
            raise DuplicateSaleItemError(
                f"Product ID {product_id} is included more than once in the sale."
            )
        seen_products.add(product_id)
        if quantity <= 0:
            raise InvalidStockChangeError(
                f"Quantity for product ID {product_id} must be greater than zero."
            )

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with conn:
        sale_cursor = conn.execute(
            "INSERT INTO sales (sale_date) VALUES (?);",
            (timestamp,),
        )
        sale_id = sale_cursor.lastrowid

        for product_id, quantity in items:
            prod = conn.execute(
                "SELECT id, name, unit_price, quantity_in_stock FROM products WHERE id = ?;",
                (product_id,),
            ).fetchone()
            if prod is None:
                raise ProductNotFoundError(f"Product ID {product_id} does not exist.")

            if prod["quantity_in_stock"] < quantity:
                raise InsufficientStockError(
                    f"Not enough stock for '{prod['name']}'. Requested {quantity}, but only {prod['quantity_in_stock']} in stock."
                )

            # Insert line item snapshotting the current price
            conn.execute(
                """
                INSERT INTO sale_items (sale_id, product_id, quantity, price_at_sale)
                VALUES (?, ?, ?, ?);
                """,
                (sale_id, product_id, quantity, prod["unit_price"]),
            )

            # Reduce product stock
            conn.execute(
                "UPDATE products SET quantity_in_stock = quantity_in_stock - ? WHERE id = ?;",
                (quantity, product_id),
            )

            # Log stock movement for the sale
            conn.execute(
                """
                INSERT INTO stock_movements (product_id, change_amount, reason, created_at)
                VALUES (?, ?, 'sale', ?);
                """,
                (product_id, -quantity, timestamp),
            )

        return sale_id


def backup_database(source_conn: sqlite3.Connection, backup_path: str | Path) -> None:
    """Create a live backup of the database to the specified file path."""
    dest_path = Path(backup_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(dest_path) as dest_conn:
        source_conn.backup(dest_conn)


def restore_database(backup_path: str | Path, target_conn: sqlite3.Connection) -> None:
    """Restore database contents from a backup file into the target connection."""
    source_path = Path(backup_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Backup file '{backup_path}' does not exist.")
    with sqlite3.connect(source_path) as source_conn:
        source_conn.backup(target_conn)



