# session/

Session persistence backed by KohakuVault. Stores everything needed to
resume an agent or terrarium in a single `.kohakutr` file (SQLite): conversation
snapshots, append-only event logs, channel message history, sub-agent
conversations, scratchpad state, token usage, and full-text search indexes.
`SessionOutput` is an output module that captures all agent events without
modifying the processing loop. `resume.py` rebuilds agents from saved
state; engine-level terrarium resume lives in `terrarium/resume.py`.

## Files

| File                    | Description                                                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `__init__.py`           | Re-exports `SessionStore`                                                                                                                  |
| `store.py`              | `SessionStore`: persistent storage with 8 table groups (meta, state, events, channels, subagents, jobs, conversation, fts) via KohakuVault |
| `store_fork.py`         | Fork / branch primitive for `SessionStore`                                                                                                 |
| `store_counters.py`, `store_protocol.py`, `token_views.py`, `version.py` | Store helpers: counter restore, helper protocols, read-side token-usage views, format versioning |
| `reader.py`             | `SessionReader`: read a finished `.kohakutr` without spelunking                                                                            |
| `readonly_view.py`, `readonly_worker.py` | Selective snapshot reads: isolated SQLite worker owns source locks; the host decodes selected rows in memory |
| `output.py`             | `SessionOutput`: output module that records text chunks, tool activity, and processing state to the store                                  |
| `resume.py`             | `resume_agent` / `detect_session_type`: rebuild from a `.kohakutr` file, inject saved conversation and scratchpad (engine-level terrarium resume lives in `terrarium/resume.py`) |
| `resume_target.py`      | Resume-only successor resolution, format companions, identity checks, and already-running target lookup; historical reads retain the requested file |
| `attach.py`, `agent_attach.py`, `attachment_service.py` | Attach/detach a store to a live agent (compat re-exports + service)                                       |
| `session.py`            | Async wrapper around a running agent + `SessionStore`                                                                                      |
| `artifacts.py`          | Session-local artifact helpers                                                                                                             |
| `rollup.py`             | Per-turn rollup helpers                                                                                                                    |
| `sync.py`               | Session event mirroring across the Laboratory layer                                                                                       |
| `memory.py`, `embedding.py` | `SessionMemory` FTS5 + vector search; embedding providers                                                                              |
| `history.py`            | Event-history normalization                                                                                                                |
| `errors.py`, `migrations/` | Session-level exceptions; format migrations                                                                                             |

## Reading live sessions

`SessionReadView` keeps one read-only transaction in a separate Python process.
The standalone `readonly_worker.py` imports only the standard library and sends
selected rows through private pipes, in batches bounded by row count and payload
size. The parent uses KohakuVault only to decode those rows in an in-memory
vault. Closing the view closes its cursors, source connection, pipes, and child.

Do not replace this process boundary with a same-process `sqlite3.connect()` on
a live session. KohakuVault can embed a different SQLite library from CPython's
`sqlite3`. On POSIX, the independent libraries do not share connection/lock
bookkeeping even though their file locks belong to the same process. A reader
can reset or invalidate WAL shared memory still mapped by the writer; concurrent
reads and writes reproduced native `SIGBUS` crashes on macOS. Drive sidecars
avoid sharing the session database but do not protect direct session readers.

The worker reads committed WAL data and retains a consistent snapshot while the
live writer continues. `immutable=1` would ignore WAL updates, and copying a
database and its WAL separately would not give a coherent live snapshot. The
selective protocol avoids copying an entire large session for a metadata read.

## Dependencies

- `kohakuterrarium.builtins.inputs` (create_builtin_input, for resume IO)
- `kohakuterrarium.builtins.outputs` (create_builtin_output, for resume IO)
- `kohakuterrarium.core.agent` (Agent)
- `kohakuterrarium.core.config_serde` (unpack_agent_config)
- `kohakuterrarium.core.conversation` (Conversation)
- `kohakuterrarium.laboratory.protocols` (LabNotifier / LabRegistrar, for sync)
- `kohakuterrarium.modules.input.base` / `modules.output.base`
- `kohakuterrarium.packages.resolve` (resolve_any_path)
- `kohakuterrarium.utils.logging`
- Third-party: `kohakuvault` (KVault, TextVault)
