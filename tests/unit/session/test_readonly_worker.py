"""Bound isolated-reader batches by row count and retained payload size."""

import sqlite3
from contextlib import closing

from kohakuterrarium.session.readonly_worker import _batch


def test_batch_retains_order_and_limits_rows_and_bytes():
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE events (key INTEGER, value BLOB)")
        connection.executemany(
            "INSERT INTO events VALUES (?, ?)", [(i, b"small") for i in range(75)]
        )
        with closing(connection.execute("SELECT * FROM events ORDER BY key")) as rows:
            first = _batch(rows)
            assert first == [(i, b"small") for i in range(32)]
            assert first + _batch(rows) + _batch(rows) == [
                (i, b"small") for i in range(75)
            ]
            assert _batch(rows) == []
        connection.execute("DELETE FROM events")
        payload = b"x" * (700 * 1024)
        connection.executemany(
            "INSERT INTO events VALUES (?, ?)", [(i, payload) for i in range(3)]
        )
        with closing(connection.execute("SELECT * FROM events ORDER BY key")) as rows:
            assert _batch(rows) == [(0, payload), (1, payload)]
            assert _batch(rows) == [(2, payload)]
