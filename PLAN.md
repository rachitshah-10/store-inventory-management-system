# Project Plan: Store Inventory Management System

This document outlines the design for the inventory management system. It covers the database tables and rules, how multi-step changes are handled safely, and the plan for branches and releases.

---

## 1. Database Tables and Constraints

The database uses SQLite in `STRICT` mode so columns enforce correct data types.

### `suppliers`
* **Purpose**: Stores vendor information so supplier details are not repeated across products.
* **Columns**:
  * `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  * `name`: TEXT NOT NULL
  * `contact_email`: TEXT NOT NULL
* **Rules**: Name and email are required.

### `products`
* **Purpose**: Tracks inventory items, pricing, on-hand counts, and reorder levels.
* **Columns**:
  * `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  * `sku`: TEXT NOT NULL UNIQUE
  * `name`: TEXT NOT NULL
  * `category`: TEXT NOT NULL
  * `supplier_id`: INTEGER NOT NULL REFERENCES suppliers(id)
  * `unit_price`: INTEGER NOT NULL CHECK (unit_price >= 0)
  * `quantity_in_stock`: INTEGER NOT NULL CHECK (quantity_in_stock >= 0)
  * `reorder_level`: INTEGER NOT NULL CHECK (reorder_level >= 0)
* **Rules**:
  * SKU must be unique across all products.
  * Prices are stored as whole cents ($10.99 is stored as 1099).
  * Price, stock count, and reorder level cannot be negative.
  * Each product must reference a valid supplier ID.

### `sales`
* **Purpose**: Represents a completed customer checkout.
* **Columns**:
  * `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  * `sale_date`: TEXT NOT NULL
* **Rules**: Date cannot be blank.

### `sale_items`
* **Purpose**: Records each item sold within a sale, locking in the price charged at the time of sale.
* **Columns**:
  * `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  * `sale_id`: INTEGER NOT NULL REFERENCES sales(id)
  * `product_id`: INTEGER NOT NULL REFERENCES products(id)
  * `quantity`: INTEGER NOT NULL CHECK (quantity > 0)
  * `unit_price`: INTEGER NOT NULL CHECK (unit_price >= 0)
* **Rules**:
  * Must connect to an existing sale and an existing product.
  * Quantity must be at least 1.
  * Price charged cannot be negative.

### `stock_movements`
* **Purpose**: An audit log tracking every increase or decrease in stock.
* **Columns**:
  * `id`: INTEGER PRIMARY KEY AUTOINCREMENT
  * `product_id`: INTEGER NOT NULL REFERENCES products(id)
  * `change_amount`: INTEGER NOT NULL CHECK (change_amount != 0)
  * `reason`: TEXT NOT NULL CHECK (reason IN ('restock', 'adjustment', 'sale'))
  * `created_at`: TEXT NOT NULL
* **Rules**:
  * Change amount cannot be zero.
  * Reason must be one of: `'restock'`, `'adjustment'`, or `'sale'`.

### Indexes
* Index on `products(supplier_id)` to speed up product-supplier joins.
* Index on `sale_items(product_id)` to speed up checking if a product has sales history before attempting deletion.

---

## 2. Transactions and Rollbacks

Inventory and sales updates involve multiple steps happening at the same time - such as deducting stock, creating a receipt, and logging an audit entry. These actions must run as an all-or-nothing package. When restocking items, adjusting counts for damage, or recording customer sales, every step must succeed completely. If any part fails—like attempting to sell an item that is out of stock or entering a negative count—the system automatically cancels and rolls back the entire operation. This guarantees no half-saved sales or missing stock counts occur.

---

## 3. Release and Branching Plan

The project will be built incrementally on separate feature branches and brought into `main` through pull requests after passing tests and linting. Development is broken down into distinct stages: creating the database and seed data, adding product management and search, writing reports, building transactional sales and stock tracking, packaging the application with a terminal menu and Docker, and finally adding a low-stock alert banner. The project will be tagged at version 1.0.0 for the first complete release, and version 1.1.0 after adding the alert banner, including testing rollbacks to confirm data stays intact between versions.
