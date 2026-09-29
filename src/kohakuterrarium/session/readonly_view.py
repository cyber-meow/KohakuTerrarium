"""Read selective snapshots with SQLite locks isolated from the host's KVault.

The child owns the source WAL/SHM transaction; the host decodes selected values
only in memory. The process boundary is part of the storage safety contract.
"""

import pickle
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

from kohakuvault import KVault

from kohakuterrarium.utils.fs_path import coerce_fs_path
from kohakuterrarium.utils.logging import get_logger

logger = get_logger(__name__)

_TABLES = frozenset({"meta", "events", "state"})


class SessionReadView:
    """One consistent, selectively decoded snapshot of an existing session."""

    def __init__(self, path: str | Path) -> None:
        source = coerce_fs_path(path).expanduser().resolve(strict=True)
        self._process = None
        self._decoder = None
        self._closed = False
        try:
            self._process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-u",
                    str(Path(__file__).with_name("readonly_worker.py")),
                    source.as_uri(),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            self._tables = self._receive()
            self._decoder = KVault(":memory:", enable_wal=False, cache_kb=1024)
            self._decoder.enable_auto_pack()
        except BaseException:
            self.close()
            raise

    def _receive(self):
        try:
            status, result = pickle.load(self._process.stdout)
        except (EOFError, OSError) as exc:
            self.close()
            raise RuntimeError("Session reader process exited unexpectedly") from exc
        if status == "error":
            name, message = result
            error = getattr(sqlite3, name, sqlite3.DatabaseError)
            if not isinstance(error, type) or not issubclass(error, Exception):
                error = sqlite3.DatabaseError
            raise error(message)
        return result

    def _request(self, operation: str, args):
        if self._closed:
            raise RuntimeError("SessionReadView is closed")
        try:
            pickle.dump((operation, args), self._process.stdin, protocol=4)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self.close()
            raise RuntimeError("Session reader process exited unexpectedly") from exc
        return self._receive()

    def _rows(self, sql: str, args: tuple = ()) -> Iterator[tuple]:
        cursor = self._request("scan", (sql, args))
        try:
            while rows := self._request("next", cursor):
                yield from rows
        finally:
            if not self._closed:
                self._request("close_cursor", cursor)

    def _decode(self, value: bytes) -> Any:
        # Bytes are stored verbatim by auto-pack; reading invokes the native
        # header/encoding decoder. No source-file handle reaches KohakuVault.
        self._decoder[b"value"] = value
        return self._decoder[b"value"]

    def get(self, table: str, key: str, default: Any = None) -> Any:
        if table not in _TABLES:
            raise ValueError(f"unsupported session table: {table}")
        if table not in self._tables:
            return default
        row = self._request(
            "one", (f'SELECT value FROM "{table}" WHERE key = ?', (key.encode(),))
        )
        if row is not None:
            try:
                return self._decode(row[0])
            except Exception as exc:
                logger.warning(
                    "Unreadable session value", table=table, key=key, error=str(exc)
                )
        return default

    def items(self, table: str, *, prefix: str = "") -> Iterator[tuple[str, Any]]:
        if table not in _TABLES:
            raise ValueError(f"unsupported session table: {table}")
        if table not in self._tables:
            return
        lower = prefix.encode()
        with closing(
            self._rows(
                f'SELECT key, value FROM "{table}" WHERE key >= ? AND key < ? ORDER BY key',
                (lower, lower + b"\xff"),
            )
        ) as rows:
            for key, value in rows:
                name = key.decode("utf-8", errors="replace")
                try:
                    decoded = self._decode(value)
                except Exception as exc:
                    logger.warning(
                        "Unreadable session value",
                        table=table,
                        key=name,
                        error=str(exc),
                    )
                    continue
                yield name, decoded

    def load_meta(self, *, discover_agents: bool = True) -> dict[str, Any]:
        meta = dict(self.items("meta"))
        known = list(meta.get("agents") or [])
        if discover_agents and "events" in self._tables:
            # Namespace discovery reads keys only, never the event payloads.
            with closing(self._rows("SELECT key FROM events ORDER BY key")) as rows:
                for (raw_key,) in rows:
                    parts = raw_key.decode("utf-8", errors="replace").rsplit(":e", 1)
                    if len(parts) != 2:
                        continue
                    agent = parts[0]
                    if (
                        agent != "terrarium"
                        and ":attached:" not in agent
                        and agent not in known
                    ):
                        known.append(agent)
        meta["agents"] = known
        return meta

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self._process
        try:
            if process is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                finally:
                    process.stdout.close()
        finally:
            if self._decoder is not None:
                self._decoder.close()
                self._decoder = None

    def __enter__(self) -> "SessionReadView":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
