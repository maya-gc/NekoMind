"""Thread-safe access to the bridge's local SQLite journal."""

from threading import RLock


class _Rows:
    """Rows already fetched while the journal lock was held."""

    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _JournalConnection:
    """Serialize every use of the shared SQLite journal connection.

    The bridge touches the journal from the serial thread, the analysis pool
    and the ops pool. ``check_same_thread=False`` allows that but does not make
    concurrent use safe; interleaved calls raised ``OperationalError: not an
    error`` intermittently (seen on Windows on 09/11/2026). Results are fetched
    under the lock, so callers keep using ``execute(...).fetchone()``.
    """

    def __init__(self, connection):
        self._connection = connection
        self._lock = RLock()

    def execute(self, sql, params=()):
        with self._lock:
            return _Rows(self._connection.execute(sql, params).fetchall())

    def commit(self):
        with self._lock:
            self._connection.commit()

    def close(self):
        with self._lock:
            self._connection.close()
