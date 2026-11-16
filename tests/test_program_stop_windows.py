"""A stop that lands in a narrow window of the pinned-program route stays a stop. Linux."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hypersearch import program as route, program_contract as contract, study_usage
from hypersearch.interruption import Interrupted
from hypersearch.store import Store
from program_fixture import make_program
from test_program import source


@unittest.skipUnless(sys.platform.startswith("linux"), "process groups are a POSIX facility")
class StopWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        previous = signal.signal(signal.SIGTERM, lambda number, frame: None)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)

    def execute(self, bundle, core, consumer):
        with patch("hypersearch.study.CORE_ROOT", core):
            return route.execute(contract.wrapper(bundle), consumer_root=consumer,
                                 database=self.root / "r.sqlite", export=self.root / "out")

    def test_a_stop_after_the_child_is_reaped_releases_the_task_and_commits_nothing(self):
        core, consumer, bundle = make_program(self.root)
        real, fired = os.waitstatus_to_exitcode, []

        def stop_once_reaped(status):  # wait4 has reaped the child; its return code is not yet set
            if not fired:
                fired.append(1); signal.raise_signal(signal.SIGTERM)
            return real(status)
        with patch.object(study_usage.os, "waitstatus_to_exitcode", stop_once_reaped):
            with self.assertRaises(Interrupted) as caught:
                self.execute(bundle, core, consumer)
        self.assertEqual(caught.exception.result["execution"], "interrupted")
        kinds = [event["kind"] for event in Store.existing(self.root / "r.sqlite").snapshot()["events"]]
        self.assertNotIn("completed", kinds)
        self.assertIn("interrupted", kinds)
        self.assertFalse((self.root / "out").exists() and any((self.root / "out").rglob("*.json")))
        self.assertEqual(caught.exception.signum, signal.SIGTERM)  # the command line passes it on

    def test_a_stop_inside_popen_is_taken_once_the_group_can_be_killed(self):
        core, consumer, bundle = make_program(self.root, source("import time; time.sleep(30)"), timeout=60)
        real, pids = subprocess._fork_exec, []

        def fork_exec(args, *rest):  # after the fork, before Popen returns
            pid = real(args, *rest)
            if not pids and "program.py" in repr(args):
                pids.append(pid); signal.raise_signal(signal.SIGTERM)
            return pid
        with patch.object(subprocess, "_fork_exec", fork_exec):
            with self.assertRaises(Interrupted) as caught:
                self.execute(bundle, core, consumer)
        self.assertEqual(caught.exception.result["task_state"], "pending")
        with self.assertRaises(ChildProcessError):  # killed and reaped by the route, not left running
            os.waitpid(pids[0], os.WNOHANG)


if __name__ == "__main__":
    unittest.main()
