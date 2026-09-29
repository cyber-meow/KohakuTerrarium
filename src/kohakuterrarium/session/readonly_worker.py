"""Serve selective SQLite reads over private parent/child pipes."""

import pickle
import sqlite3
import sys

_BATCH_ROWS = 32
_BATCH_BYTES = 1024 * 1024


def _send(status: str, value) -> None:
    pickle.dump((status, value), sys.stdout.buffer, protocol=4)
    sys.stdout.buffer.flush()


def _batch(cursor: sqlite3.Cursor) -> list[tuple]:
    rows = []
    size = 0
    while len(rows) < _BATCH_ROWS and size < _BATCH_BYTES:
        row = cursor.fetchone()
        if row is None:
            break
        rows.append(row)
        size += sum(len(value) for value in row if isinstance(value, (bytes, str)))
    return rows


def serve(uri: str) -> None:
    """Keep one read transaction open until the parent closes its input pipe."""
    connection = None
    cursors: dict[int, sqlite3.Cursor] = {}
    try:
        connection = sqlite3.connect(uri + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        _send("ok", tables)
        sequence = 0
        while True:
            try:
                operation, args = pickle.load(sys.stdin.buffer)
            except EOFError:
                break
            try:
                if operation == "one":
                    cursor = connection.execute(*args)
                    try:
                        result = cursor.fetchone()
                    finally:
                        cursor.close()
                elif operation == "scan":
                    sequence += 1
                    cursors[sequence] = connection.execute(*args)
                    result = sequence
                elif operation == "next":
                    result = _batch(cursors[args])
                elif operation == "close_cursor":
                    cursor = cursors.pop(args, None)
                    if cursor is not None:
                        cursor.close()
                    result = None
                else:
                    raise ValueError(f"Unsupported reader operation: {operation}")
                _send("ok", result)
            except Exception as exc:
                _send("error", (type(exc).__name__, str(exc)[:2000]))
    except Exception as exc:
        _send("error", (type(exc).__name__, str(exc)[:2000]))
    finally:
        for cursor in cursors.values():
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    serve(sys.argv[1])
