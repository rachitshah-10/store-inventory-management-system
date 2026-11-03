# Inventory Management System

A CLI inventory management system for a small hardware store built with Python and SQLite. It replaces the store's spreadsheet with a relational database enforcing strict data types, foreign keys, non-negative checks, and atomic transactions.

---

## Configuration & How to Run

- **Database Path**: Set the `INVENTORY_DB` environment variable to point to a database file. If not set, it defaults to `inventory.db` in the project root.

### Setup & Seeding
```bash
pip install -r requirements.txt
python seed_db.py
```
Seed output:
```text
Table suppliers: 4 rows
Table products: 12 rows
Table sales: 5 rows
Table sale_items: 12 rows
Table stock_movements: 0 rows
```

### Run Menu
```bash
python main.py
```

### Run Tests
```bash
pytest
```
Output:
```text
============================== 31 passed in 0.05s ==============================
```

---

## Sample Data Reports

Running the reports on the initial seed data produces the following results:

### 1. Stock Value by Supplier
```text
Bright Paints & Finishes: $1719.86
Apex Tool Supply: $1290.07
Fasteners Direct: $569.37
Timber & Lumber Co: $239.60
```

### 2. Low Stock Products (Stock <= Reorder Level)
```text
Drywall Screws 100pk (SCRW-DRYW-01) | Stock: 8 | Reorder: 15 | Units Short: 7
Hex Bolts 25pk (BOLT-HEX-01)       | Stock: 5 | Reorder: 10 | Units Short: 5
```

### 3. Sales by Product (Highest Revenue First)
```text
White Primer 1gal    | Sold: 2 | Revenue: $64.00
Claw Hammer 16oz     | Sold: 3 | Revenue: $59.97
Drywall Screws 100pk | Sold: 5 | Revenue: $37.45
Wood Screws 100pk    | Sold: 3 | Revenue: $26.97
Hand Saw 15in        | Sold: 1 | Revenue: $24.50
Hex Bolts 25pk       | Sold: 2 | Revenue: $23.98
2x4 Pine Stud 8ft    | Sold: 3 | Revenue: $17.97
Paint Roller Kit     | Sold: 1 | Revenue: $14.25
Needle Nose Pliers   | Sold: 1 | Revenue: $12.99
Paint Brush 2in      | Sold: 1 | Revenue: $6.50
```

### 4. Products Never Sold
```text
Drop Cloth Tarp 9x12 (PNT-TRP-01) | Category: Paint | Price: $10.99
Torpedo Level 9in (TOOL-LEV-01)   | Category: Tools | Price: $15.75
```

---

## Transaction Rollback Demonstration (Failed Sale)

Sales run inside a single `with conn:` transaction block. If any item in the sale fails (e.g. asking for 50 drywall screws when only 8 are in stock), all earlier line items and movements roll back automatically.

**State Before:**
```text
Sales count: 5
Sale items count: 12
Stock movements count: 0
Product 1 stock: 50
Product 2 stock: 8
```

**Failing Call:**
```python
record_sale(conn, [(1, 2), (2, 50)])
```
Error raised:
```text
InsufficientStockError: Not enough stock for 'Drywall Screws 100pk'. Requested 50, but only 8 in stock.
```

**State After (rolled back):**
```text
Sales count: 5
Sale items count: 12
Stock movements count: 0
Product 1 stock: 50
Product 2 stock: 8
```
Nothing partial was saved, and product 1's stock was not changed.

---

## Docker Deployment & Persistence Check

### Build the Image
```bash
docker build -t inventory-system:1.1.0 .
docker tag inventory-system:1.1.0 inventory-system:latest
```
Real build output:
```text
 => [internal] load build definition from Dockerfile
 => [internal] load .dockerignore
 => [1/5] FROM docker.io/library/python:3.11-slim
 => [2/5] WORKDIR /app
 => [3/5] COPY requirements.txt .
 => [4/5] RUN pip install --no-cache-dir -r requirements.txt
 => [5/5] COPY . .
 => naming to docker.io/library/inventory-system:1.1.0
 => naming to docker.io/library/inventory-system:latest
```

### Persistence Across Containers
Running with a volume mount preserves data when containers stop:

```bash
mkdir -p data

# Container 1: Seed data into mounted volume
docker run --rm -v $(pwd)/data:/data -e INVENTORY_DB=/data/inventory.db inventory-system:1.1.0 python seed_db.py

# Container 2: Restock product 1 by 20 units
docker run --rm -v $(pwd)/data:/data -e INVENTORY_DB=/data/inventory.db inventory-system:1.1.0 python -c "from inventory_db import connect, restock; conn = connect(); restock(conn, 1, 20); conn.close()"

# Container 3: Verify the restocked quantity persists
docker run --rm -v $(pwd)/data:/data -e INVENTORY_DB=/data/inventory.db inventory-system:1.1.0 python -c "from inventory_db import connect; conn = connect(); row = conn.execute('SELECT quantity_in_stock FROM products WHERE id = 1;').fetchone(); print(f'Persistent Stock: {row[0]} units'); conn.close()"
```
Output:
```text
Persistent Stock: 70 units
```

---

## Database Backup and Restore

### How to Back Up and Restore
```python
from inventory_db import connect, backup_database, restore_database

# Create backup
with connect("inventory.db") as conn:
    backup_database(conn, "backup.db")

# Restore backup
with connect("inventory.db") as conn:
    restore_database("backup.db", conn)
```

### Backup Check Output
```bash
python -c "
from inventory_db import connect
back = connect('backup.db')
print('Integrity check:', back.execute('PRAGMA integrity_check;').fetchone()[0])
tables = ['suppliers', 'products', 'sales', 'sale_items', 'stock_movements']
for t in tables:
    count = back.execute(f'SELECT COUNT(*) FROM {t};').fetchone()[0]
    print(f'{t}: {count} rows')
"
```
Output:
```text
Integrity check: ok
suppliers: 4 rows
products: 12 rows
sales: 5 rows
sale_items: 12 rows
stock_movements: 0 rows
```

---

## Rollback from 1.1.0 to 1.0.0

To roll back code to 1.0.0 while keeping volume data intact:

```bash
git checkout v1.0.0
docker run -it --rm -v $(pwd)/data:/data -e INVENTORY_DB=/data/inventory.db inventory-system:1.0.0
```

Rollback output:
```text
Hardware Store Inventory
------------------------
1. Search products
2. Look up product
3. Add product
4. Restock
5. Record a sale
6. Reports
7. Back up database
8. Exit
Enter choice (1-8): 
```
The application runs without the 1.1.0 low-stock alert banner, and all products and sales data in `/data/inventory.db` remain intact.

---

## Self-Review

### What I Would Do Differently
If I had to rebuild this from scratch, I would probably split `inventory_db.py` into a couple of smaller files (like separating the reporting queries from the core product logic). Having all the functions in one file made it a bit long to scroll through while working on it.

I would also add simple command line flags so you could run things directly instead of having to click through the interactive menu every time. Having to answer multiple prompts in a row gets a bit tedious when you just want to quickly check low stock or add a single item.

### Area of Uncertainty for Reviewer
One thing I am unsure about is my `record_sale` function. Right now, I check stock levels in Python inside a `for` loop and raise an exception if anything is short, which triggers the `with conn:` rollback. It works and all tests pass, but I'd like the reviewer to check if doing the check in Python is the standard way to handle multi-item transactions in SQLite, or if there is a cleaner way to let the database handle more of that validation.

