"""Releasing a stopped attempt and abandoning a dead one: the attempt stays charged, nothing is deleted."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from hypersearch.store import Store, StaleLease

HOLDER = {"pid": 4321, "started": 99, "boot": "synthetic-boot", "host": "synthetic-host"}
# The table definitions of 0.8.0. An earlier release opening a newer database sees exactly these.
EARLIER_TABLES = {
    "budget": "CREATE TABLE budget (id INTEGER PRIMARY KEY CHECK(id=1), maximum INTEGER NOT NULL, spent INTEGER NOT NULL)",
    "tasks": "CREATE TABLE tasks (id TEXT PRIMARY KEY, spec TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL, worker TEXT, fence INTEGER NOT NULL DEFAULT 0, expires REAL)",
    "results": "CREATE TABLE results (task_id TEXT PRIMARY KEY REFERENCES tasks(id), fence INTEGER NOT NULL, result TEXT NOT NULL, digest TEXT NOT NULL)",
    "events": "CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, task_id TEXT NOT NULL, fence INTEGER NOT NULL, time REAL NOT NULL)",
}


def dead(holder):
    return "dead"


def details(snapshot):
    return [(e["kind"], e["fence"], None if e["detail"] is None else json.loads(e["detail"])) for e in snapshot["events"]]


class StoreReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "queue.sqlite"
        self.now = 100.0
        self.store = Store(self.path, max_attempts=5, clock=lambda: self.now, holder=HOLDER)
        self.store.submit("a", {"input": 1})

    def test_an_interrupted_attempt_is_released_charged_and_fenced(self):
        old = self.store.acquire("w", 3600, task_id="a")
        self.store.interrupt(old, "SIGTERM")
        state = self.store.snapshot()
        self.assertEqual((state["tasks"][0]["state"], state["tasks"][0]["fence"], state["budget"]["spent"]), ("pending", 1, 1))
        self.assertEqual(details(state), [("submitted", 0, None), ("acquired", 1, {"holder": HOLDER}),
                                          ("interrupted", 1, {"signal": "SIGTERM"})])
        with self.assertRaises(StaleLease):                       # released: it can neither complete nor release again
            self.store.complete(old, {"value": 1})
        with self.assertRaises(StaleLease):
            self.store.interrupt(old, "SIGTERM")
        new = self.store.acquire("w", 3600, task_id="a")          # at once, not after the hour
        self.assertEqual((new.fence, self.store.snapshot()["budget"]["spent"]), (2, 2))
        with self.assertRaises(StaleLease):
            self.store.complete(old, {"value": 1})
        with self.assertRaises(StaleLease):
            self.store.interrupt(old, "SIGTERM")
        self.store.complete(new, {"value": 2})
        self.assertEqual([r["fence"] for r in self.store.snapshot()["results"]], [2])

    def test_an_interruption_refuses_a_bad_signal_name_and_changes_nothing(self):
        lease = self.store.acquire("w", 60, task_id="a")
        before = self.store.snapshot()
        for name in ("", None, "x" * 300):
            with self.assertRaises(ValueError):
                self.store.interrupt(lease, name)
        self.assertEqual(self.store.snapshot(), before)

    def test_abandon_frees_only_a_lease_whose_recorded_holder_is_dead(self):
        self.store.submit("b", {"input": 2})
        done = self.store.acquire("w", 60, task_id="b")
        self.store.complete(done, {"value": "kept"})
        lease = self.store.acquire("w", 3600, task_id="a")
        before = self.store.snapshot()
        for task, fence, state, reason in (("a", 1, lambda h: "alive", "still running"),
                                           ("a", 1, lambda h: "unknown", "cannot be checked"),
                                           ("a", 2, dead, "not the current lease"),
                                           ("a", 0, dead, "not the current lease"),
                                           ("b", 1, dead, "completed"),
                                           ("missing", 1, dead, "no such task")):
            with self.assertRaisesRegex(ValueError, reason):
                self.store.abandon(task, fence, "launcher was killed", holder_state=state)
            self.assertEqual(self.store.snapshot(), before)
        seen = []
        record = self.store.abandon("a", 1, "launcher was killed", holder_state=lambda h: seen.append(h) or "dead")
        self.assertEqual((seen, record["holder"], record["fence"]), ([HOLDER], HOLDER, 1))
        after = self.store.snapshot()
        self.assertEqual(after["events"][:len(before["events"])], before["events"])    # appended, never rewritten
        self.assertEqual(after["results"], before["results"])                          # no result is removed
        self.assertEqual(details(after)[-1], ("abandoned", 1, {"reason": "launcher was killed", "holder": HOLDER}))
        self.assertEqual((after["tasks"][0]["state"], after["tasks"][0]["fence"], after["budget"]["spent"]), ("pending", 1, 2))
        with self.assertRaisesRegex(ValueError, "not leased"):                          # pending now
            self.store.abandon("a", 1, "again", holder_state=dead)
        with self.assertRaises(StaleLease):
            self.store.complete(lease, {"value": "late"})
        self.assertEqual(self.store.acquire("w", 60, task_id="a").fence, 2)

    def test_a_lease_without_a_recorded_holder_cannot_be_abandoned(self):
        anonymous = Store(self.path, max_attempts=5, clock=lambda: self.now)      # as a review grant or an earlier release
        anonymous.acquire("reviewer", 3600, task_id="a")
        before = anonymous.snapshot()
        with self.assertRaisesRegex(ValueError, "records no holder"):
            anonymous.abandon("a", 1, "reviewer went away", holder_state=dead)
        self.assertEqual(anonymous.snapshot(), before)
        for reason in ("", None, "x" * 300):
            with self.assertRaises(ValueError):
                self.store.abandon("a", 1, reason, holder_state=dead)

    def test_a_holder_is_validated_before_anything_is_written(self):
        for holder in ({}, {**HOLDER, "pid": 0}, {**HOLDER, "pid": True}, {**HOLDER, "started": -1},
                       {**HOLDER, "boot": ""}, {**HOLDER, "extra": 1}, "4321"):
            with self.assertRaises(ValueError):
                Store(Path(self.tmp.name) / "other.sqlite", max_attempts=5, holder=holder)

    def test_an_existing_database_opens_with_its_own_ceiling_and_a_missing_one_is_refused(self):
        self.assertEqual(Store.existing(self.path).snapshot()["budget"], {"maximum": 5, "spent": 0})
        missing = Path(self.tmp.name) / "missing.sqlite"
        with self.assertRaisesRegex(ValueError, "does not exist"):
            Store.existing(missing)
        self.assertFalse(missing.exists())
        foreign = Path(self.tmp.name) / "foreign.sqlite"
        sqlite3.connect(foreign).close()
        with self.assertRaisesRegex(ValueError, "not a task database"):
            Store.existing(foreign)


class EarlierDatabaseTests(unittest.TestCase):
    """A database written by 0.8.0 opens unchanged in meaning, and a newer one stays readable by 0.8.0."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "earlier.sqlite"

    def test_an_earlier_database_gains_details_and_keeps_its_rows(self):
        db = sqlite3.connect(self.path)
        for sql in EARLIER_TABLES.values():
            db.execute(sql)
        db.execute("INSERT INTO budget VALUES (1, 3, 1)")
        db.execute("INSERT INTO tasks VALUES ('a', '{}', 'd', 'running', 'w', 1, 1e12)")
        db.execute("INSERT INTO events(kind,task_id,fence,time) VALUES ('submitted','a',0,1),('acquired','a',1,2)")
        db.commit(); db.close()
        store = Store(self.path, max_attempts=3)
        state = store.snapshot()
        self.assertEqual(details(state), [("submitted", 0, None), ("acquired", 1, None)])
        self.assertEqual((state["tasks"][0]["state"], state["budget"]), ("running", {"maximum": 3, "spent": 1}))
        with self.assertRaisesRegex(ValueError, "records no holder"):   # nobody can say that holder is dead
            store.abandon("a", 1, "launcher was killed", holder_state=dead)
        self.assertIsNone(store.acquire("w", 60, task_id="a"))          # still leased until it expires
        self.assertEqual(self.tables(), EARLIER_TABLES)

    def test_a_newer_database_keeps_the_earlier_tables_and_a_released_task_is_acquirable_by_them(self):
        store = Store(self.path, max_attempts=3, holder=HOLDER)
        store.submit("a", {})
        store.interrupt(store.acquire("w", 60, task_id="a"), "SIGINT")
        self.assertEqual(self.tables(), EARLIER_TABLES)
        db = sqlite3.connect(self.path)                                  # the 0.8.0 acquire query
        row = db.execute("SELECT id, fence FROM tasks WHERE (state='pending' OR (state='running' AND expires<=?)) "
                         "AND (? IS NULL OR id=?) ORDER BY id LIMIT 1", (200.0, "a", "a")).fetchone()
        db.close()
        self.assertEqual(row, ("a", 1))

    def tables(self):
        db = sqlite3.connect(self.path)
        rows = dict(db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN "
                               "('budget','tasks','results','events')").fetchall())
        db.close()
        return rows


if __name__ == "__main__":
    unittest.main()
