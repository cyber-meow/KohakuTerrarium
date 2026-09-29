"""Read-only session snapshots use the real SQLite and KohakuVault codecs."""

from contextlib import closing
import sqlite3
import subprocess
import sys
import textwrap

import pytest

from kohakuterrarium.session.readonly_view import SessionReadView
from kohakuterrarium.session.store import SessionStore


def test_view_reads_wal_and_keeps_one_snapshot(tmp_path):
    path = tmp_path / "snapshot %20 #.kohakutr"
    with closing(SessionStore(path)) as store:
        store.init_meta("sid", "agent", "", "", ["alice"])
        store.meta["nested"] = {"items": [None, True, 4.5, "汉字"]}
        store.append_event("discovered", "user_input", {"content": "new agent"})
        store.append_event("alice:attached:helper:1", "text", {"content": "private"})
        store.flush()
        with SessionReadView(path.as_uri()) as reader:
            meta = reader.load_meta()
            assert meta["agents"] == ["alice", "discovered"]
            assert meta["nested"] == {"items": [None, True, 4.5, "汉字"]}
            store.meta["nested"] = {"items": ["new value"]}
            assert reader.get("meta", "nested") == meta["nested"]
            assert reader.get("state", "missing", "default") == "default"
            assert (
                list(reader.items("events", prefix="discovered:e"))[0][1]["content"]
                == "new agent"
            )
            with pytest.raises(ValueError, match="unsupported session table"):
                reader.get("other", "key")
        with SessionReadView(path) as reader:
            assert reader.get("meta", "nested") == {"items": ["new value"]}


def test_missing_view_does_not_create_database(tmp_path):
    path = tmp_path / "missing.kohakutr"
    with pytest.raises(FileNotFoundError):
        SessionReadView(path)
    assert not path.exists()


def test_invalid_source_reaps_failed_reader(tmp_path):
    path = tmp_path / "broken.kohakutr"
    path.write_bytes(b"not a database")
    reader = SessionReadView.__new__(SessionReadView)
    with pytest.raises(sqlite3.DatabaseError, match="not a database"):
        reader.__init__(path)
    assert reader._process.poll() is not None
    assert reader._process.stdin.closed and reader._process.stdout.closed
    assert path.read_bytes() == b"not a database"
    reader.close()


def test_worker_exit_raises_and_closes_transport(tmp_path):
    with closing(SessionStore(tmp_path / "exit.kohakutr")) as store:
        store.init_meta("sid", "agent", "", "", ["alice"])
        reader = SessionReadView(store.path)
        reader._process.kill()
        reader._process.wait(timeout=5)
        with pytest.raises(RuntimeError, match="reader process exited"):
            reader.get("meta", "agents")
        assert reader._closed and reader._decoder is None
        reader.close()
        with pytest.raises(RuntimeError, match="closed"):
            reader.get("meta", "agents")
        store.meta["still_writable"] = "yes"
        assert store.meta["still_writable"] == "yes"


def test_partial_scans_close_and_source_stays_readonly(tmp_path):
    path = tmp_path / "scan.kohakutr"
    with closing(SessionStore(path)) as store:
        store.init_meta("sid", "agent", "", "", ["alice"])
        for index in range(75):
            store.append_event("alice", "user_input", {"content": str(index)})
        store.flush()
        reader = SessionReadView(store.path)
        assert len(list(reader.items("events", prefix="alice:e"))) == 75
        rows = reader.items("events", prefix="alice:e")
        assert next(rows)[1]["content"] == "0"
        rows.close()
        assert reader.load_meta()["agents"] == ["alice"]
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader._request("one", ('DELETE FROM "meta"', ()))
        rows = reader.items("events", prefix="alice:e")
        next(rows)
        reader.close()
        rows.close()
        assert reader._process.poll() == 0
        with SessionReadView(store.path) as fresh:
            assert fresh.get("meta", "agents") == ["alice"]
    path.unlink()
    assert not path.exists()


def test_live_writer_survives_concurrent_read_views(tmp_path):
    code = textwrap.dedent("""
        import faulthandler
        import sys
        import threading
        from kohakuvault import KVault
        from kohakuterrarium.session.readonly_view import SessionReadView

        faulthandler.enable()
        path = sys.argv[1]
        vaults = [KVault(path, table=name) for name in ('meta', 'events', 'state')]
        for vault in vaults:
            vault.enable_auto_pack()
        vaults[0]['agents'] = ['synthetic']
        stop = threading.Event()
        errors = []
        def reader():
            try:
                for _ in range(30):
                    with SessionReadView(path) as view:
                        assert view.get('meta', 'agents') == ['synthetic']
            except BaseException as exc:
                errors.append(repr(exc))
            finally:
                stop.set()
        thread = threading.Thread(target=reader)
        thread.start()
        written = 0
        while not stop.is_set():
            vaults[0]['sequence'] = written
            assert vaults[0].get('sequence') == written
            written += 1
        thread.join()
        assert written > 0 and not errors, errors
        with SessionReadView(path) as view:
            assert view.get('meta', 'sequence') == written - 1
        for vault in vaults:
            vault.close()
        """)
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "concurrent.kohakutr")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
