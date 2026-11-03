# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-11-03

### Added
- Low-stock alert banner at menu startup displaying the count of products currently at or below their reorder level.

## [1.0.0] - 2026-11-03

### Added
- Initial release of the Store Inventory Management System.
- SQLite database schema with STRICT mode tables, foreign key constraints, and check constraints for non-negative values.
- Database seeding script with sample suppliers, products, and sales records.
- Product CRUD operations (add, get with supplier join, update price, delete with sales history check).
- Product search with keyword matching and combinable filters.
- Inventory and sales reports (stock value by supplier, low stock items, sales by product, products never sold).
- Atomic transaction management for restock, adjustment, and sales recording.
- Live database backup and restore functions using SQLite's backup API.
- Interactive terminal menu in `main.py`.
- Dockerfile and container deployment configuration with volume persistence.
- GitHub Actions CI workflow with test and docker-build jobs.

