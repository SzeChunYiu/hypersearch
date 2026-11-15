"""How the program route ends its child: the process group, a lost exit status and the input pipe. Linux."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from hypersearch import program as route, program_contract as contract
from hypersearch.study_json import encode, parse
from hypersearch.study_usage import Meter, feed, reap
from program_fixture import make_program
from study_fixture import launch
from test_program import source

HOLDS = 'print(json.dumps({"holds": True, "summary": {}}))'
WAITS = "import time\ntime.sleep(30)"     # bounded: a timeout that is never enforced fails instead of hanging


def alive(pid, marker):
    """True while that process still runs the marked command; a zombie or a reused process id is not it."""
    try:
        return marker.encode() in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False


def ignore_sigchld():
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)


class ProgramReapingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_program(self, body, sigchld=signal.SIG_DFL, **options):
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root, source(body), **options)
        previous = signal.signal(signal.SIGCHLD, sigchld)    # after the fixture: its git commands need their statuses
        self.addCleanup(signal.signal, signal.SIGCHLD, previous)
        with patch("hypersearch.study.CORE_ROOT", core):
            result = route.execute(contract.wrapper(bundle), consumer_root=consumer, database=root / "tasks.sqlite",
                                   export=root / "receipts")
        return result, parse(Path(result["receipt_path"]).read_bytes(), 1 << 21)

    def test_what_the_program_left_in_its_group_is_killed_after_a_successful_run(self):
        marker = "hypersearch-left-behind-" + self.root.name
        body = ("import subprocess\nchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)  # %s'])\n"
                'print(json.dumps({"holds": True, "summary": {"pid": child.pid}}))' % marker)
        result, receipt = self.run_program(body)
        pid = receipt["outcome"]["verification"]["summary"]["pid"]
        self.addCleanup(lambda: alive(pid, marker) and os.kill(pid, signal.SIGKILL))
        self.assertEqual(result["outcome_status"], "PROGRAM_HOLDS")
        deadline = time.monotonic() + 5
        while alive(pid, marker) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(alive(pid, marker), "a process the program started survived its successful run")

    def test_a_timeout_stays_incomplete_when_the_exit_status_is_lost(self):
        result, receipt = self.run_program(WAITS, signal.SIG_IGN, timeout=1)   # the kernel reaps the killed program
        self.assertEqual((result["outcome_status"], receipt["diagnostics"]), ("INCOMPLETE", "program timeout"))

    def test_the_command_line_restores_exit_statuses_when_sigchld_is_inherited_ignored(self):
        for body, options, status, code in ((HOLDS, {}, "PROGRAM_HOLDS", 0), (WAITS, {"timeout": 1}, "INCOMPLETE", 2)):
            root = Path(tempfile.mkdtemp(dir=self.root))
            core, consumer, bundle = make_program(root, source(body), **options)
            path = root / "bundle.json"; path.write_bytes(encode(bundle))
            result = subprocess.run([sys.executable, *launch(root / "cache"), "-m", "hypersearch", "run-program",
                                     "--bundle", str(path), "--consumer-root", str(consumer), "--db", str(root / "tasks.sqlite"),
                                     "--export", str(root / "receipts")],
                                    env={"PATH": os.defpath, "PYTHONPATH": str(core / "src")}, capture_output=True,
                                    text=True, timeout=120, preexec_fn=ignore_sigchld)   # inherited across exec
            printed = json.loads(result.stdout)
            self.assertEqual((result.returncode, printed["outcome_status"]), (code, status), result.stderr)
            self.assertTrue(printed["usage"]["max_rss_kilobytes"] > 0, printed)   # wait4 saw the program itself

    def test_input_for_a_child_that_has_already_exited_is_not_an_error(self):
        # Through the route the input (at most 4 KiB) is written as the program starts, before it can exit,
        # so this guard cannot be reached there reliably; it is exercised directly.
        for size in (16, 1048576):                                  # buffered until close, and written at once
            child = subprocess.Popen([sys.executable, "-I", "-c", "raise SystemExit(3)"], stdin=subprocess.PIPE)
            os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)  # exited, not yet reaped: nobody reads the pipe
            feed(child, b"x" * size)
            reap(child, Meter(), time.monotonic(), 30)
            self.assertEqual((child.stdin.closed, child.returncode), (True, 3), size)


if __name__ == "__main__":
    unittest.main()
