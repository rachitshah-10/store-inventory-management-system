"""Terminal menu interface for the hardware store inventory management system."""

import contextlib
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

import inventory_db as db


def get_text(prompt: str, required: bool = False) -> str:
    """Read a string from the user, re-prompting if required."""
    while True:
        val = input(prompt).strip()
        if required and not val:
            print("This cannot be empty, please try again.")
            continue
        return val


def get_int(prompt: str, required: bool = True) -> int | None:
    """Read an integer from the user with a friendly error on bad input."""
    while True:
        val = input(prompt).strip()
        if not val:
            if not required:
                return None
            print("Please enter a number.")
            continue
        try:
            return int(val)
        except ValueError:
            print("That's not a valid number. Please enter digits only.")


def get_price_in_cents(prompt: str, required: bool = True) -> int | None:
    """Read a dollar price and convert it to whole cents."""
    while True:
        val = input(prompt).strip().lstrip("$")
        if not val:
            if not required:
                return None
            print("Please enter a price.")
            continue
        try:
            dollars = float(val)
            if dollars < 0:
                print("Price cannot be negative.")
                continue
            return int(round(dollars * 100))
        except ValueError:
            print("Please enter a valid price, like 9.99 or 15.")


def do_search(conn: sqlite3.Connection) -> None:
    """Search products by keyword and optional filters."""
    print("\n--- Search Products ---")
    query = get_text("Search term (name, SKU, or supplier, or press Enter for all): ")
    category = get_text("Category (or Enter to skip): ")
    max_price = get_price_in_cents("Max price (e.g. 25.00, or Enter to skip): ", required=False)
    in_stock = get_text("In-stock items only? (y/n): ").lower().startswith("y")
    low_stock = get_text("Low-stock items only? (y/n): ").lower().startswith("y")

    results = db.search_products(
        conn,
        text=query or None,
        category=category or None,
        max_price=max_price,
        in_stock_only=in_stock,
        low_stock_only=low_stock,
    )

    if not results:
        print("\nNo products found matching those criteria.")
        return

    print(f"\nFound {len(results)} matching product(s):")
    print("ID | SKU | Name | Category | Price | Stock | Reorder")
    print("-" * 65)
    for p in results:
        price = db.format_cents(p["unit_price"])
        print(f"{p['id']} | {p['sku']} | {p['name']} | {p['category']} | {price} | {p['quantity_in_stock']} | {p['reorder_level']}")


def do_lookup(conn: sqlite3.Connection) -> None:
    """Look up one product by ID and show its details."""
    print("\n--- Look Up Product ---")
    prod_id = get_int("Enter product ID: ")
    if prod_id is None:
        return

    product = db.get_product(conn, prod_id)
    if not product:
        print(f"Product #{prod_id} not found.")
        return

    print("\nProduct Details:")
    print(f"  ID: {product['id']}")
    print(f"  SKU: {product['sku']}")
    print(f"  Name: {product['name']}")
    print(f"  Category: {product['category']}")
    print(f"  Supplier: {product['supplier_name']} (ID: {product['supplier_id']})")
    print(f"  Price: {db.format_cents(product['unit_price'])}")
    print(f"  Stock: {product['quantity_in_stock']} units")
    print(f"  Reorder Level: {product['reorder_level']} units")


def do_add_product(conn: sqlite3.Connection) -> None:
    """Add a new product to the database."""
    print("\n--- Add Product ---")
    sku = get_text("SKU: ", required=True)
    name = get_text("Name: ", required=True)
    category = get_text("Category: ", required=True)
    supplier_id = get_int("Supplier ID: ")
    price = get_price_in_cents("Price (e.g. 12.99): ")
    stock = get_int("Quantity in stock: ")
    reorder = get_int("Reorder level: ")

    if any(v is None for v in (supplier_id, price, stock, reorder)):
        return

    try:
        new_id = db.add_product(conn, sku, name, category, supplier_id, price, stock, reorder)
        print(f"\nAdded '{name}' successfully with ID {new_id}!")
    except db.DuplicateSkuError:
        print(f"\nError: SKU '{sku}' is already in use by another product.")
    except db.UnknownSupplierError:
        print(f"\nError: Supplier ID {supplier_id} does not exist.")
    except db.InventoryError as err:
        print(f"\nError: {err}")
    except sqlite3.Error as err:
        print(f"\nDatabase error: {err}")


def do_restock(conn: sqlite3.Connection) -> None:
    """Restock a product by adding more units."""
    print("\n--- Restock ---")
    prod_id = get_int("Enter product ID: ")
    if prod_id is None:
        return

    amount = get_int("How many units arrived? ")
    if amount is None:
        return

    try:
        movement_id = db.restock(conn, prod_id, amount)
        product = db.get_product(conn, prod_id)
        current = product["quantity_in_stock"] if product else "unknown"
        print(f"\nRestocked {amount} units. New stock is {current} (logged movement #{movement_id}).")
    except db.InventoryError as err:
        print(f"\nError: {err}")
    except sqlite3.Error as err:
        print(f"\nDatabase error: {err}")


def do_sale(conn: sqlite3.Connection) -> None:
    """Record a sale for one or more products."""
    print("\n--- Record a Sale ---")
    items = []

    while True:
        prod_id = get_int("Product ID to sell: ")
        if prod_id is None:
            break

        qty = get_int("Quantity to sell: ")
        if qty is None:
            break

        items.append((prod_id, qty))

        more = get_text("Add another item to this receipt? (y/n): ")
        if not more.lower().startswith("y"):
            break

    if not items:
        print("Sale cancelled (no items).")
        return

    try:
        sale_id = db.record_sale(conn, items)
        print(f"\nSale #{sale_id} completed successfully for {len(items)} line item(s).")
    except db.InventoryError as err:
        print(f"\nSale cancelled: {err}")
    except sqlite3.Error as err:
        print(f"\nDatabase error during sale: {err}")


def do_reports(conn: sqlite3.Connection) -> None:
    """Display the reports submenu."""
    while True:
        print("\n--- Reports ---")
        print("1. Stock Value by Supplier")
        print("2. Low Stock Products")
        print("3. Sales by Product")
        print("4. Products Never Sold")
        print("5. Back to Main Menu")

        choice = get_text("Pick a report (1-5): ")
        if choice == "1":
            rows = db.report_stock_value_by_supplier(conn)
            print("\n=== Stock Value by Supplier ===")
            for r in rows:
                print(f"  {r['supplier_name']}: {db.format_cents(r['total_value'])}")
        elif choice == "2":
            rows = db.report_low_stock(conn)
            print("\n=== Low Stock Products ===")
            if not rows:
                print("  All products have enough stock!")
            else:
                for r in rows:
                    print(f"  {r['name']} ({r['sku']}) - In Stock: {r['quantity_in_stock']}, Reorder at: {r['reorder_level']} (Need {r['units_short']} more)")
        elif choice == "3":
            rows = db.report_sales_by_product(conn)
            print("\n=== Sales by Product ===")
            if not rows:
                print("  No sales recorded yet.")
            else:
                for r in rows:
                    print(f"  {r['name']} - Sold: {r['units_sold']}, Revenue: {db.format_cents(r['total_revenue'])}")
        elif choice == "4":
            rows = db.report_never_sold(conn)
            print("\n=== Products Never Sold ===")
            if not rows:
                print("  All products have been sold at least once!")
            else:
                for r in rows:
                    print(f"  {r['name']} ({r['sku']}) - {r['category']}, {db.format_cents(r['unit_price'])}")
        elif choice == "5":
            break
        else:
            print("Please pick an option from 1 to 5.")


def do_backup(conn: sqlite3.Connection) -> None:
    """Make a backup copy of the database."""
    print("\n--- Back Up Database ---")
    default_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    dest = get_text(f"Backup file path (press Enter for '{default_name}'): ")
    if not dest:
        dest = default_name

    try:
        db.backup_database(conn, dest)
        print(f"\nBackup created successfully at: {Path(dest).resolve()}")
    except Exception as err:
        print(f"\nFailed to create backup: {err}")


def print_menu() -> None:
    """Print the main menu options."""
    print("\nHardware Store Inventory")
    print("------------------------")
    print("1. Search products")
    print("2. Look up product")
    print("3. Add product")
    print("4. Restock")
    print("5. Record a sale")
    print("6. Reports")
    print("7. Back up database")
    print("8. Exit")


def main() -> None:
    """Run the interactive store menu."""
    try:
        conn = db.connect()
    except sqlite3.Error as err:
        print(f"Could not connect to database: {err}")
        sys.exit(1)

    with contextlib.closing(conn):
        db.init_db(conn)

        while True:
            print_menu()
            choice = get_text("Enter choice (1-8): ")

            try:
                if choice == "1":
                    do_search(conn)
                elif choice == "2":
                    do_lookup(conn)
                elif choice == "3":
                    do_add_product(conn)
                elif choice == "4":
                    do_restock(conn)
                elif choice == "5":
                    do_sale(conn)
                elif choice == "6":
                    do_reports(conn)
                elif choice == "7":
                    do_backup(conn)
                elif choice == "8":
                    print("Goodbye!")
                    break
                else:
                    print("Invalid choice. Please enter a number between 1 and 8.")
            except (KeyboardInterrupt, EOFError):
                print("\nAction cancelled.")
            except Exception as err:
                print(f"\nSomething went wrong: {err}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting. Goodbye!")
        sys.exit(0)
