"""Product database journaling policy for the linked SQLite runtime.

SQLite's WAL-reset fix shipped in 3.51.3, with 3.44.6/3.50.7 backports:
https://sqlite.org/wal.html#walresetbug
"""
import sqlite3


class DatabaseSafetyError(sqlite3.OperationalError):
    """Database could not be opened under the required integrity policy."""


def journal_mode(version_info=None, *, prefer_wal=True):
    version = sqlite3.sqlite_version_info if version_info is None else version_info
    if not isinstance(version, (tuple, list)) or not version or any(type(n) is not int or n < 0 for n in version):
        return "delete"
    version = tuple((list(version)+[0, 0, 0])[:3])
    fixed = version >= (3, 51, 3) or (3, 50, 7) <= version < (3, 51, 0) or (3, 44, 6) <= version < (3, 45, 0)
    return "wal" if prefer_wal and fixed else "delete"


def configure_database(connection, *, prefer_wal=True):
    """Migrate via SQLite itself, never delete/rewrite journal sidecar files.

    Call before transactions. Every connection rechecks the effective mode;
    another process or an older package must not silently re-enable unsafe WAL.
    """
    requested = journal_mode(prefer_wal=prefer_wal)
    try:
        current = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if current == "memory":
            # In-memory databases have no disk WAL/reset/checkpoint race.
            selected = current
        elif current == requested:
            selected = current
        else:
            try:
                selected = str(connection.execute("PRAGMA journal_mode="+requested.upper()).fetchone()[0]).lower()
            except sqlite3.DatabaseError:
                if requested != "wal": raise
                # Patched engines may still run on a filesystem without WAL.
                selected = str(connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower()
            if selected not in {requested, "delete"}:
                raise DatabaseSafetyError("Unsafe database journal mode")
        # NORMAL + rollback journal can lose durability on power failure. FULL
        # is connection-local, so set it on readers and writers alike.
        connection.execute("PRAGMA synchronous=FULL")
        return selected
    except sqlite3.DatabaseError:
        raise DatabaseSafetyError("Indra could not open its database safely. Close other Indra instances and retry; if it persists, inspect Runtime diagnostics. No journal files were deleted.") from None


def open_database(path, *, prefer_wal=True, **options):
    connection = sqlite3.connect(path, **options)
    try:
        configure_database(connection, prefer_wal=prefer_wal)
        return connection
    except BaseException:
        connection.close()
        raise
