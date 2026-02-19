"""Pytest fixtures and Supabase mock for testing."""
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


def make_mock_store():
    """Create in-memory store and mock Supabase client."""

    store = defaultdict(list)

    def add_row(table: str, data: dict) -> dict:
        row = dict(data)
        if "id" not in row:
            row["id"] = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        row.setdefault("created_at", now)
        row.setdefault("updated_at", now)
        store[table].append(row)
        return row

    def find_rows(table: str, filters: dict) -> list:
        rows = list(store.get(table, []))
        for col, val in filters.items():
            rows = [r for r in rows if str(r.get(col)) == str(val)]
        return rows

    class TableMock:
        def __init__(self, table_name: str):
            self._table = table_name
            self._filters = {}
            self._order = None
            self._single = False
            self._update_data = None
            self._delete = False

        def insert(self, data: dict):
            row = add_row(self._table, data)
            m = MagicMock()
            m.execute.return_value.data = [row]
            return m

        def select(self, cols: str = "*"):
            self._op = "select"
            return self

        def update(self, data: dict):
            self._op = "update"
            self._update_data = data
            return self

        def delete(self):
            self._op = "delete"
            self._delete = True
            return self

        def eq(self, col: str, val: Any):
            self._filters[col] = val
            return self

        def order(self, col: str, desc: bool = False):
            self._order = (col, desc)
            return self

        def maybe_single(self):
            self._single = True
            return self

        def execute(self):
            rows = find_rows(self._table, self._filters)
            if self._op == "select":
                if self._single:
                    data = rows[0] if rows else None
                else:
                    if self._order:
                        col, desc = self._order
                        rows = sorted(rows, key=lambda r: r.get(col, ""), reverse=desc)
                    data = rows
            elif self._op == "update":
                if not rows:
                    return MagicMock(data=None)
                for r in rows:
                    r.update(self._update_data or {})
                data = rows
            else:  # delete
                if not rows:
                    return MagicMock(data=None)
                for r in rows:
                    store[self._table].remove(r)
                data = rows
            return MagicMock(data=data)

    class SupabaseMock:
        def table(self, name: str):
            return TableMock(name)

    return store, SupabaseMock()


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Provide mocked Supabase with fresh in-memory store per test."""
    store, supabase = make_mock_store()
    # Patch where get_supabase is used (routers import it from database)
    patches = [
        patch("routers.providers.get_supabase", return_value=supabase),
        patch("routers.rooms.get_supabase", return_value=supabase),
        patch("routers.clients.get_supabase", return_value=supabase),
        patch("routers.appointments.get_supabase", return_value=supabase),
    ]
    for p in patches:
        p.start()
    yield store, supabase
    for p in patches:
        p.stop()
