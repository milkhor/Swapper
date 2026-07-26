import os
import sys

import pytest

# Make the project root importable when running pytest from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as db


@pytest.fixture
async def fresh_db(tmp_path, monkeypatch):
    """Point the DB layer at an empty temp database and initialise the schema."""
    path = str(tmp_path / "test_swaps.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    await db.init_db()
    return db
