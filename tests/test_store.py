from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import tempfile
from pathlib import Path
import threading
import unittest

from hypersearch.store import Store, StaleLease


class StoreTests(unittest.TestCase):
    def test_exact_task_acquisition_never_runs_unrelated_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "exact.sqlite", max_attempts=3)
            store.submit("a-unrelated", {"input": 1})
            store.submit("z-selected", {"input": 2})
            before = store.snapshot()
            self.assertIsNone(store.acquire("worker", task_id="missing"))
            self.assertEqual(store.snapshot(), before)
            lease = store.acquire("worker", task_id="z-selected")
            self.assertEqual(lease.task_id, "z-selected")
            state = store.snapshot()
            self.assertEqual(state["tasks"][0]["state"], "pending")
            self.assertEqual(state["budget"]["spent"], 1)
            store.complete(lease, {"done": True})
            self.assertIsNone(store.acquire("worker", task_id="z-selected"))
            self.assertEqual(store.snapshot()["budget"]["spent"], 1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "queue.db"
        self.now = 100.0
        self.store = Store(self.path, max_attempts=3, clock=lambda: self.now)

    def test_frozen_spec_and_reopen_budget(self):
        self.store.submit("a", {"domain": "math"})
        self.store.submit("a", {"domain": "math"})
        with self.assertRaises(ValueError):
            self.store.submit("a", {"domain": "other"})
        self.store.acquire("worker")
        other = Store(self.path, max_attempts=3)
        self.assertEqual(other.snapshot()["budget"]["spent"], 1)
        with self.assertRaises(ValueError):
            Store(self.path, max_attempts=100)

    def test_expiry_fence_and_duplicate_results(self):
        self.store.submit("a", {"domain": "math"})
        old = self.store.acquire("w", 1)
        self.now = 101
        with self.assertRaises(StaleLease):
            self.store.complete(old, {"value": 1})
        new = self.store.acquire("w", 10)
        self.assertGreater(new.fence, old.fence)
        with self.assertRaises(StaleLease):
            self.store.complete(old, {"value": 1})
        with self.assertRaises(StaleLease):
            self.store.complete(replace(new, spec_digest="tampered"), {"value": 1})
        self.store.complete(new, {"value": 2})
        with self.assertRaises(StaleLease):
            self.store.complete(new, {"value": 3})
        snap = self.store.snapshot()
        self.assertEqual(len(snap["results"]), 1)
        self.assertEqual(snap["results"][0]["result"], '{"value":2}')
        self.assertEqual([e["kind"] for e in snap["events"]], ["submitted", "acquired", "acquired", "completed"])

    def test_budget_exhaustion_never_refunds_expired_attempts(self):
        self.store.submit("a", {})
        for _ in range(3):
            self.assertIsNotNone(self.store.acquire("w", 1))
            self.now += 2
        self.assertIsNone(self.store.acquire("w"))
        self.assertEqual(self.store.snapshot()["budget"]["spent"], 3)
        self.assertEqual(self.store.snapshot()["results"], [])

    def test_concurrent_claim_has_one_owner(self):
        self.store.submit("a", {})
        barrier = threading.Barrier(8)
        def acquire(i):
            barrier.wait()
            return self.store.acquire(f"w{i}")
        with ThreadPoolExecutor(max_workers=8) as pool:
            leases = list(pool.map(acquire, range(8)))
        self.assertEqual(sum(lease is not None for lease in leases), 1)
        self.assertEqual(self.store.snapshot()["budget"]["spent"], 1)

    def test_concurrent_budget_is_global(self):
        for i in range(8):
            self.store.submit(str(i), {})
        with ThreadPoolExecutor(max_workers=8) as pool:
            leases = list(pool.map(lambda i: self.store.acquire(str(i)), range(8)))
        self.assertEqual(sum(lease is not None for lease in leases), 3)
        self.assertEqual(self.store.snapshot()["budget"]["spent"], 3)

    def test_invalid_values_fail_before_mutation(self):
        for spec in ({"v": float("nan")}, {1: "value"}, {"v": (1, 2)}):
            with self.assertRaises(ValueError):
                self.store.submit("a", spec)
        self.store.submit("a", {})
        for seconds in (True, 0, -1, float("inf"), float("nan"), 86401):
            with self.assertRaises(ValueError):
                self.store.acquire("w", seconds)
        self.assertEqual(self.store.snapshot()["budget"]["spent"], 0)
        lease = self.store.acquire("w")
        with self.assertRaises(ValueError):
            self.store.complete(lease, {"value": float("nan")})
        self.assertEqual(self.store.snapshot()["results"], [])


if __name__ == "__main__":
    unittest.main()
