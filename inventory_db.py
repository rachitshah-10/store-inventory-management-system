"""Database connection and initialization module for the inventory system."""

import os
import sqlite3
from pathlib import Path


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
