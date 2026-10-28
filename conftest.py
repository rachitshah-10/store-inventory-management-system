"""Pytest configuration and shared fixtures for inventory management system tests."""

import sqlite3
import pytest
from inventory_db import connect, init_db


@pytest.fixture
def db_conn() -> sqlite3.Connection:
    """Provide a fresh in-memory SQLite database connection with tables created."""
    conn = connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()
