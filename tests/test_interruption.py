"""Stop signals while a lease is held, and who holds it. In-process; the signals are sent to this process."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from hypersearch import holders
from hypersearch.interruption import Interrupted, held, stopping
from hypersearch.store import Store
from hypersearch.study import execute
from hypersearch.study_contract import wrapper
from study_fixture import make

LINUX = sys.platform.startswith("linux")


class Recorder:
    def __init__(self):
        self.seen = []

    def __call__(self, signum, frame):
        self.seen.append(signum)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.recorder = Recorder()
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):    # never the defaults: a slip would end the run
            self.addCleanup(signal.signal, number, signal.signal(number, self.recorder))

    def test_a_stop_while_armed_interrupts_and_a_second_one_is_absorbed(self):
        with stopping() as stop:
            with self.assertRaises(Interrupted) as caught:
                with stop.armed():
                    signal.raise_signal(signal.SIGTERM)
                    self.fail("not interrupted")
            self.assertEqual(caught.exception.signum, signal.SIGTERM)
            signal.raise_signal(signal.SIGINT)                     # during clean-up: neither raised nor passed on
        self.assertEqual(self.recorder.seen, [])
        self.assertIs(signal.getsignal(signal.SIGTERM), self.recorder)

    def test_a_stop_while_held_waits_for_the_end_of_the_hold(self):
        with stopping() as stop:
            with self.assertRaises(Interrupted) as caught:
                with stop.armed():
                    with held():
                        signal.raise_signal(signal.SIGHUP)
                        reached = True
            self.assertTrue(reached)
            self.assertEqual(caught.exception.signum, signal.SIGHUP)

    def test_a_stop_before_arming_interrupts_when_armed(self):
        with stopping() as stop:
            signal.raise_signal(signal.SIGINT)
            with self.assertRaises(Interrupted):
                with stop.armed():
                    self.fail("armed with a stop already received")
        self.assertEqual(self.recorder.seen, [])

    def test_a_stop_while_unarmed_is_passed_on_once_the_guard_ends(self):
        with stopping():
            signal.raise_signal(signal.SIGTERM)
            self.assertEqual(self.recorder.seen, [])
        self.assertEqual(self.recorder.seen, [signal.SIGTERM])

    def test_an_ignored_signal_stays_ignored(self):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)               # as under nohup
        with stopping() as stop:
            self.assertIs(signal.getsignal(signal.SIGHUP), signal.SIG_IGN)
            with stop.armed():
                signal.raise_signal(signal.SIGHUP)
        self.assertEqual(self.recorder.seen, [])

    def test_outside_the_main_thread_nothing_is_installed(self):
        observed = []

        def worker():
            with stopping() as stop:
                observed.append(signal.getsignal(signal.SIGTERM))
                with stop.armed(), held():
                    pass
        thread = threading.Thread(target=worker); thread.start(); thread.join()
        self.assertEqual(observed, [self.recorder])


@unittest.skipUnless(LINUX, "process identity is read from /proc")
class HolderTests(unittest.TestCase):
    def test_this_process_is_alive_and_a_changed_identity_is_not_it(self):
        me = holders.identity()
        self.assertEqual(set(me), {"pid", "started", "boot", "host"})
        self.assertEqual((me["pid"], holders.state(me)), (os.getpid(), "alive"))
        self.assertEqual(holders.state({**me, "started": me["started"] + 1}), "dead")   # a reused process id
        self.assertEqual(holders.state({**me, "boot": "another-boot"}), "dead")          # rebooted since
        self.assertEqual(holders.state({**me, "host": me["host"] + "-other"}), "unknown")

    def test_an_exited_or_unreaped_process_is_dead(self):
        child = subprocess.Popen([sys.executable, "-I", "-c", "pass"])
        recorded = holders.identity(child.pid)
        os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)        # a zombie: exited, not yet reaped
        self.assertEqual(holders.state(recorded), "dead")
        child.wait()
        self.assertEqual(holders.state(recorded), "dead")

    def test_without_proc_nothing_is_recorded_and_nothing_is_known(self):
        me = holders.identity()
        with patch.object(holders, "PROC", Path("/nonexistent-proc")):
            self.assertIsNone(holders.identity())
            self.assertEqual(holders.state(me), "unknown")


class ExecutorInterruptionTests(unittest.TestCase):
    """The shared executor, here through the supplied-witness route: every frozen route behaves alike."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core, self.consumer, self.bundle = make(self.root)
        self.addCleanup(patch.stopall); patch("hypersearch.study.CORE_ROOT", self.core).start()
        self.recorder = Recorder()
        self.addCleanup(signal.signal, signal.SIGTERM, signal.signal(signal.SIGTERM, self.recorder))

    def run_study(self):
        return execute(wrapper(self.bundle), consumer_root=self.consumer, database=self.root / "run.sqlite",
                       export=self.root / "receipts")

    def test_a_stop_during_the_run_releases_the_task_for_an_immediate_relaunch(self):
        def stopped(bundle, core, meter=None):
            signal.raise_signal(signal.SIGTERM)
            raise AssertionError("the run went on after a stop")
        with patch("hypersearch.study.run_verifier", stopped):
            with self.assertRaises(Interrupted) as caught:
                self.run_study()
        result = caught.exception.result
        self.assertEqual((result["execution"], result["signal"], result["fence"], result["lease_released"],
                          result["task_state"], result["budget"]),
                         ("interrupted", "SIGTERM", 1, True, "pending", {"maximum": 5, "spent": 1}))
        state = Store.existing(self.root / "run.sqlite").snapshot()
        self.assertEqual([e["kind"] for e in state["events"]], ["submitted", "acquired", "interrupted"])
        self.assertEqual((state["results"], self.recorder.seen), ([], []))
        self.assertFalse((self.root / "receipts").exists())
        again = self.run_study()                                   # no wait for the lease to expire
        self.assertEqual((again["execution"], again["outcome_status"]), ("completed", "VERIFIED_WITNESS"))
        state = Store.existing(self.root / "run.sqlite").snapshot()
        self.assertEqual(([r["fence"] for r in state["results"]], state["budget"]["spent"]), ([2], 2))
        if LINUX:
            acquired = [e for e in state["events"] if e["kind"] == "acquired"]
            self.assertTrue(all(f'"pid":{os.getpid()}' in e["detail"] for e in acquired))

    def test_a_stop_during_the_commit_is_passed_on_after_it(self):
        real = Store.complete

        def complete(store, lease, result):
            signal.raise_signal(signal.SIGTERM)
            self.assertEqual(self.recorder.seen, [])              # not yet: the commit is never cut in half
            return real(store, lease, result)
        with patch.object(Store, "complete", complete):
            result = self.run_study()
        self.assertEqual((result["execution"], self.recorder.seen), ("completed", [signal.SIGTERM]))
        self.assertEqual(Store.existing(self.root / "run.sqlite").snapshot()["tasks"][0]["state"], "completed")


if __name__ == "__main__":
    unittest.main()
