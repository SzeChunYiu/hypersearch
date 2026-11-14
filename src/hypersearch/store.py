"""Single-host cooperative task queue, not an authentication or sandbox boundary.

Each acquire permanently spends one attempt, including crashes and expired leases.
Lease fencing protects queue commits; it cannot fence external side effects.
Use a local filesystem, not a shared/network SQLite file. Wall-clock jumps may
expire work early or delay reclamation; fencing still rejects superseded leases.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import sqlite3
import time


def canonical_json(value):
    def validate(item):
        if isinstance(item, dict):
            if any(type(key) is not str for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                validate(child)
        elif isinstance(item, list):
            for child in item:
                validate(child)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise ValueError("only JSON values are supported")
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("identifier must be a nonempty string of at most 256 characters")
    return value


@dataclass(frozen=True)
class Lease:
    task_id: str
    worker: str
    fence: int
    expires_at: float
    spec_json: str
    spec_digest: str


class StaleLease(ValueError):
    """The lease is expired, superseded, completed, or mismatched."""


class Store:
    """Durable queue with a fixed, global attempt budget.

    submit(task_id, spec) is idempotent for identical JSON. acquire(worker,
    lease_seconds) returns a Lease or None when idle/budget exhausted.
    complete(lease, result) stores one immutable result; repeated completion
    is rejected, never silently counted as another success. Results are opaque
    records, not scientific acceptance. Only a trusted domain verifier can
    supply evidence. All callers sharing this file are assumed cooperative.
    """

    def __init__(self, path, max_attempts=100, *, clock=time.time):
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if str(path) == ":memory:":
            raise ValueError("a durable local database path is required")
        self.path, self.clock = str(path), clock
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK(id=1), maximum INTEGER NOT NULL, spent INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, spec TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL, worker TEXT, fence INTEGER NOT NULL DEFAULT 0, expires REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS results (task_id TEXT PRIMARY KEY REFERENCES tasks(id), fence INTEGER NOT NULL, result TEXT NOT NULL, digest TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, task_id TEXT NOT NULL, fence INTEGER NOT NULL, time REAL NOT NULL)")
            db.execute("INSERT OR IGNORE INTO budget VALUES (1, ?, 0)", (max_attempts,))
            if db.execute("SELECT maximum FROM budget WHERE id=1").fetchone()[0] != max_attempts:
                raise ValueError("existing budget differs; budgets cannot silently reset")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _now(self):
        now = self.clock()
        if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now) or now < 0:
            raise ValueError("clock must return a finite nonnegative timestamp")
        return now

    def submit(self, task_id, spec):
        _name(task_id)
        if not isinstance(spec, dict):
            raise ValueError("spec must be a JSON object")
        encoded = canonical_json(spec)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self._transaction() as db:
            row = db.execute("SELECT spec FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row:
                if row[0] != encoded:
                    raise ValueError("task specification is immutable")
                return digest
            db.execute("INSERT INTO tasks(id,spec,digest,state) VALUES(?,?,?,'pending')", (task_id, encoded, digest))
            db.execute("INSERT INTO events(kind,task_id,fence,time) VALUES('submitted',?,0,?)", (task_id, self._now()))
        return digest

    def acquire(self, worker, lease_seconds=60, *, task_id=None):
        _name(worker)
        if task_id is not None:
            _name(task_id)
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float)) or not math.isfinite(lease_seconds) or not 0 < lease_seconds <= 86400:
            raise ValueError("lease_seconds must be finite and in (0, 86400]")
        with self._transaction() as db:
            now = self._now()
            budget = db.execute("SELECT maximum,spent FROM budget WHERE id=1").fetchone()
            if budget["spent"] >= budget["maximum"]:
                return None
            row = db.execute(
                "SELECT * FROM tasks WHERE (state='pending' OR (state='running' AND expires<=?)) "
                "AND (? IS NULL OR id=?) ORDER BY id LIMIT 1", (now, task_id, task_id)).fetchone()
            if row is None:
                return None
            fence, expires = row["fence"] + 1, now + lease_seconds
            if not math.isfinite(expires):
                raise ValueError("lease expiry overflow")
            db.execute("UPDATE tasks SET state='running',worker=?,fence=?,expires=? WHERE id=?", (worker, fence, expires, row["id"]))
            db.execute("UPDATE budget SET spent=spent+1 WHERE id=1")
            db.execute("INSERT INTO events(kind,task_id,fence,time) VALUES('acquired',?,?,?)", (row["id"], fence, now))
            return Lease(row["id"], worker, fence, expires, row["spec"], row["digest"])

    def complete(self, lease, result):
        if not isinstance(lease, Lease):
            raise ValueError("Lease required")
        _name(lease.task_id)
        _name(lease.worker)
        if type(lease.fence) is not int or lease.fence < 1:
            raise ValueError("lease fence must be a positive integer")
        if isinstance(lease.expires_at, bool) or not isinstance(lease.expires_at, (int, float)) or not math.isfinite(lease.expires_at):
            raise ValueError("lease expiry must be finite")
        if not isinstance(result, dict):
            raise ValueError("result must be a JSON object")
        encoded = canonical_json(result)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self._transaction() as db:
            now = self._now()
            row = db.execute("SELECT * FROM tasks WHERE id=?", (lease.task_id,)).fetchone()
            if (row is None or row["state"] != "running" or row["expires"] <= now
                    or row["fence"] != lease.fence or row["worker"] != lease.worker
                    or row["expires"] != lease.expires_at or row["spec"] != lease.spec_json
                    or row["digest"] != lease.spec_digest):
                raise StaleLease("result rejected: lease is no longer current")
            db.execute("INSERT INTO results VALUES(?,?,?,?)", (lease.task_id, lease.fence, encoded, digest))
            db.execute("UPDATE tasks SET state='completed' WHERE id=?", (lease.task_id,))
            db.execute("INSERT INTO events(kind,task_id,fence,time) VALUES('completed',?,?,?)", (lease.task_id, lease.fence, now))
        return digest

    def snapshot(self):
        """Return queue records and raw results without claiming verification."""
        with self._transaction() as db:
            return {"budget": dict(db.execute("SELECT maximum,spent FROM budget WHERE id=1").fetchone()),
                    "tasks": [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY id")],
                    "results": [dict(r) for r in db.execute("SELECT * FROM results ORDER BY task_id")],
                    "events": [dict(r) for r in db.execute("SELECT * FROM events ORDER BY sequence")]}
