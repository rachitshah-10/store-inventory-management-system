"""Seed the database with initial sample hardware store data."""

import contextlib
import sqlite3

from inventory_db import connect, init_db

SUPPLIERS = [
    (1, "Fasteners Direct", "sales@fastenersdirect.com"),
    (2, "Apex Tool Supply", "orders@apextools.com"),
    (3, "Timber & Lumber Co", "support@timberco.com"),
    (4, "Bright Paints & Finishes", "hello@brightpaints.com"),
]

PRODUCTS = [
    # Hardware
    (1, "SCRW-WOOD-01", "Wood Screws 100pk", "Hardware", 1, 899, 50, 20),
    (2, "SCRW-DRYW-01", "Drywall Screws 100pk", "Hardware", 1, 749, 8, 15),
    (3, "LUMB-2X4-08", "2x4 Pine Stud 8ft", "Hardware", 3, 599, 40, 10),
    (4, "BOLT-HEX-01", "Hex Bolts 25pk", "Hardware", 1, 1199, 5, 10),
    # Tools
    (5, "TOOL-HAM-01", "Claw Hammer 16oz", "Tools", 2, 1999, 25, 5),
    (6, "TOOL-SAW-01", "Hand Saw 15in", "Tools", 2, 2450, 15, 5),
    (7, "TOOL-PLI-01", "Needle Nose Pliers", "Tools", 2, 1299, 18, 4),
    (8, "TOOL-LEV-01", "Torpedo Level 9in", "Tools", 2, 1575, 12, 3),
    # Paint
    (9, "PNT-WHT-01", "White Primer 1gal", "Paint", 4, 3200, 30, 10),
    (10, "PNT-BRS-01", "Paint Brush 2in", "Paint", 4, 650, 45, 15),
    (11, "PNT-ROL-01", "Paint Roller Kit", "Paint", 4, 1425, 22, 8),
    (12, "PNT-TRP-01", "Drop Cloth Tarp 9x12", "Paint", 4, 1099, 14, 5),
]

# 5 Sales
SALES = [
    (1, "2026-10-01 10:15:00"),
    (2, "2026-10-05 14:30:00"),
    (3, "2026-10-10 11:00:00"),
    (4, "2026-10-15 16:45:00"),
    (5, "2026-10-20 09:20:00"),
]

# 12 Sale Items
SALE_ITEMS = [
    # Sale 1 (3 items)
    (1, 1, 1, 2, 899),
    (2, 1, 5, 1, 1999),
    (3, 1, 10, 1, 650),
    # Sale 2 (2 items)
    (4, 2, 2, 5, 749),
    (5, 2, 6, 1, 2450),
    # Sale 3 (3 items)
    (6, 3, 3, 3, 599),
    (7, 3, 7, 1, 1299),
    (8, 3, 9, 2, 3200),
    # Sale 4 (2 items)
    (9, 4, 4, 2, 1199),
    (10, 4, 11, 1, 1425),
    # Sale 5 (2 items)
    (11, 5, 1, 1, 899),
    (12, 5, 5, 2, 1999),
]


def seed_database(conn: sqlite3.Connection) -> None:
    """Populate the database with sample suppliers, products, and sales records."""
    init_db(conn)

    with conn:
        # Clear existing data so seeding is reproducible
        conn.execute("DELETE FROM stock_movements;")
        conn.execute("DELETE FROM sale_items;")
        conn.execute("DELETE FROM sales;")
        conn.execute("DELETE FROM products;")
        conn.execute("DELETE FROM suppliers;")

        conn.executemany(
            "INSERT INTO suppliers (id, name, contact_email) VALUES (?, ?, ?);",
            SUPPLIERS,
        )
        conn.executemany(
            """
            INSERT INTO products (
                id, sku, name, category, supplier_id, unit_price, quantity_in_stock, reorder_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            PRODUCTS,
        )
        conn.executemany(
            "INSERT INTO sales (id, sale_date) VALUES (?, ?);",
            SALES,
        )
        conn.executemany(
            """
            INSERT INTO sale_items (
                id, sale_id, product_id, quantity, price_at_sale
            ) VALUES (?, ?, ?, ?, ?);
            """,
            SALE_ITEMS,
        )


def print_table_counts(conn: sqlite3.Connection) -> None:
    """Query and print the row count for each table in the database."""
    tables = ["suppliers", "products", "sales", "sale_items", "stock_movements"]
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) AS total FROM {table};")
        row = cursor.fetchone()
        count = row["total"] if row else 0
        print(f"Table {table}: {count} rows")


def main() -> None:
    """Run table initialization, seed data, and print final counts."""
    with contextlib.closing(connect()) as conn:
        seed_database(conn)
        print_table_counts(conn)


if __name__ == "__main__":
    main()
