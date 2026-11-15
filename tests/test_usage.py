"""Resource usage in the printed result of the frozen routes; never in a receipt. Synthetic programs only."""
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from hypersearch import census, program as route, program_contract as contract, study
from hypersearch.study_json import encode, parse
from hypersearch.study_usage import Meter, feed, reap, waited_children
from census_fixture import make_census
from program_fixture import make_program
from study_fixture import launch, make
from test_program import source

KEYS = {"wall_milliseconds", "cpu_milliseconds", "max_rss_kilobytes"}
SPIN = "import time\nstart = time.process_time()\nwhile time.process_time() - start < 0.4:\n    pass\n"
DONE = 'print(json.dumps({"holds": True, "summary": {}}))'
TOUCH = "block = bytearray(%d * 1048576)\nfor index in range(0, len(block), 4096):\n    block[index] = 1\n"   # resident, not only reserved


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_program(self, body, name, **options):
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root, source(body), **options)
        with patch("hypersearch.study.CORE_ROOT", core):
            return route.execute(contract.wrapper(bundle), consumer_root=consumer, database=self.root / (name + ".sqlite"),
                                 export=self.root / name), (core, consumer, bundle)

    def test_a_completed_program_reports_its_own_cpu_and_peak_memory(self):
        result, (core, consumer, bundle) = self.run_program(SPIN + DONE, "spin")
        usage = result["usage"]
        self.assertEqual((result["execution"], set(usage)), ("completed", KEYS))
        self.assertTrue(all(type(value) is int for value in usage.values()), usage)
        self.assertTrue(400 <= usage["cpu_milliseconds"] < 5000, usage)       # the spin, plus starting an interpreter
        self.assertTrue(usage["cpu_milliseconds"] - 100 <= usage["wall_milliseconds"] < 30000, usage)
        self.assertTrue(usage["max_rss_kilobytes"] > 0, usage)
        self.assertEqual(parse(encode(result)), result)                      # integers only: the strict parser reads it
        # The receipt has exactly the fields it had before; usage is not one of them.
        raw = Path(result["receipt_path"]).read_bytes()
        receipt = contract.trusted_receipt(raw, result["receipt_sha256"])
        self.assertEqual(set(receipt), {"schema", "execution", "execution_sha256", "task_id", "outcome", "outcome_sha256",
                                        "attempt", "runtime", "diagnostics", "replay_matches_parent"})
        self.assertEqual(set(receipt["runtime"]), {"python", "implementation", "core_commit", "elapsed_ms"})
        self.assertEqual((set(receipt["attempt"]), set(receipt["outcome"])), ({"worker", "fence"}, {"status", "verification"}))
        with patch("hypersearch.study.CORE_ROOT", core):
            again = route.execute(contract.wrapper(bundle), consumer_root=consumer, database=self.root / "spin.sqlite",
                                  export=self.root / "spin")
            replay = route.execute(contract.wrapper(bundle, parent=result["receipt_sha256"], replay_id="second"),
                                   consumer_root=consumer, database=self.root / "spin.sqlite", export=self.root / "replay",
                                   parent_receipt=receipt)
        self.assertEqual((again["execution"], "usage" in again), ("not_rerun", False))
        self.assertEqual((replay["replay_matches_parent"], set(replay["usage"])), (True, KEYS))   # usage never affects a replay

    def test_a_start_that_is_refused_reports_no_usage(self):
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root, attempts=1)
        with patch("hypersearch.study.CORE_ROOT", core):
            first = route.execute(contract.wrapper(bundle), consumer_root=consumer, database=self.root / "one.sqlite",
                                  export=self.root / "one")
            receipt = contract.trusted_receipt(Path(first["receipt_path"]).read_bytes(), first["receipt_sha256"])
            refused = route.execute(contract.wrapper(bundle, parent=first["receipt_sha256"], replay_id="second"),
                                    consumer_root=consumer, database=self.root / "one.sqlite", export=self.root / "refused",
                                    parent_receipt=receipt)
        self.assertEqual((first["execution"], "usage" in first), ("completed", True))
        self.assertEqual((refused["execution"], "usage" in refused), ("not_started", False))

    def test_peak_memory_and_waited_descendants_are_the_programs_own(self):
        result, _ = self.run_program(TOUCH % 128 + DONE, "memory")
        self.assertTrue(128 * 1024 <= result["usage"]["max_rss_kilobytes"] < 400 * 1024, result["usage"])
        small, _ = self.run_program(DONE, "small")                 # a later, smaller program is not given the earlier peak
        self.assertTrue(0 < small["usage"]["max_rss_kilobytes"] < 128 * 1024, small["usage"])
        waited = "import subprocess\nsubprocess.run([sys.executable, '-c', %r], check=True)\n" % SPIN
        result, _ = self.run_program(waited + DONE, "waited")
        self.assertTrue(result["usage"]["cpu_milliseconds"] >= 400, result["usage"])
        left = "import subprocess\nsubprocess.Popen([sys.executable, '-c', %r])\n" % SPIN
        result, _ = self.run_program(left + DONE, "left")          # a child the program did not wait for is not counted
        self.assertEqual(result["outcome_status"], "PROGRAM_HOLDS")
        self.assertTrue(result["usage"]["cpu_milliseconds"] < 400, result["usage"])

    def test_a_timeout_and_a_failure_still_report_what_was_used(self):
        result, _ = self.run_program(SPIN + "time.sleep(600)", "timeout", timeout=2)
        self.assertEqual(result["outcome_status"], "INCOMPLETE")       # what the killed program had used is still reported
        self.assertTrue(result["usage"]["wall_milliseconds"] >= 2000 and result["usage"]["cpu_milliseconds"] >= 200, result["usage"])
        result, _ = self.run_program(SPIN + "raise SystemExit(3)", "failure")
        self.assertEqual(result["outcome_status"], "EXECUTION_FAILED")
        self.assertTrue(result["usage"]["cpu_milliseconds"] >= 400, result["usage"])
        root = Path(tempfile.mkdtemp(dir=self.root))
        core, consumer, bundle = make_program(root)
        with patch("hypersearch.study.CORE_ROOT", core), patch("hypersearch.program.run_program", side_effect=OSError("no launch")):
            result = route.execute(contract.wrapper(bundle), consumer_root=consumer, database=self.root / "none.sqlite",
                                   export=self.root / "none")
        nothing = {"wall_milliseconds": 0, "cpu_milliseconds": 0, "max_rss_kilobytes": None}
        self.assertEqual((result["outcome_status"], result["usage"]), ("EXECUTION_FAILED", nothing))   # no child was waited for
        previous = signal.signal(signal.SIGCHLD, signal.SIG_IGN)   # the kernel reaps the program: its exit status is lost
        try:
            with patch("hypersearch.study.CORE_ROOT", core):
                result = route.execute(contract.wrapper(bundle), consumer_root=consumer, database=self.root / "lost.sqlite",
                                       export=self.root / "lost")
        finally:
            signal.signal(signal.SIGCHLD, previous)
        self.assertEqual((result["outcome_status"], result["usage"]), ("EXECUTION_FAILED", nothing))   # never read as exit 0

    def test_the_verifier_routes_report_usage_from_the_shared_child_counters(self):
        for built, module in ((make, study), (make_census, census)):
            root = Path(tempfile.mkdtemp(dir=self.root))
            core, consumer, bundle = built(root)
            made = module.census_route() if module is census else module.study_route()
            with patch("hypersearch.study.CORE_ROOT", core):
                result = study.execute(made.wrapper(bundle), consumer_root=consumer, database=root / "tasks.sqlite",
                                       export=root / "receipts", route=made)
            usage = result["usage"]
            self.assertEqual((result["execution"], set(usage)), ("completed", KEYS))
            self.assertTrue(0 < usage["cpu_milliseconds"] <= usage["wall_milliseconds"] + 100, usage)
            self.assertTrue(usage["max_rss_kilobytes"] is None or usage["max_rss_kilobytes"] > 0, usage)
            self.assertEqual(parse(encode(result)), result)

    def test_the_shared_high_water_mark_is_reported_only_when_this_call_raised_it(self):
        size = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss // 1024 + 48    # megabytes above every child so far
        first, second, third = Meter(), Meter(), Meter()
        with waited_children(first):
            subprocess.run([sys.executable, "-I", "-c", TOUCH % size], check=True)
        with waited_children(second):
            subprocess.run([sys.executable, "-I", "-c", "pass"], check=True)
        with waited_children(third):
            subprocess.run([sys.executable, "-I", "-c", TOUCH % (size + 48) + SPIN], check=True)
        self.assertTrue(first.report()["max_rss_kilobytes"] >= size * 1024, first.report())
        self.assertEqual(second.report()["max_rss_kilobytes"], None)          # the mark did not move: not this child's
        self.assertTrue(third.report()["max_rss_kilobytes"] >= (size + 48) * 1024, third.report())
        self.assertTrue(third.report()["cpu_milliseconds"] >= 400 > second.report()["cpu_milliseconds"], third.report())
        self.assertEqual(Meter().report(), {"wall_milliseconds": 0, "cpu_milliseconds": 0, "max_rss_kilobytes": None})

    def test_reap_keeps_the_exit_status_and_the_timeout(self):
        for code, expected in (("raise SystemExit(7)", 7), ("import os\nos.kill(os.getpid(), 9)", -9)):
            child = subprocess.Popen([sys.executable, "-I", "-c", code], stdin=subprocess.PIPE)
            feed(child, b"x" * 4096)                               # never read: a broken pipe is not an error
            reap(child, Meter(), time.monotonic(), 30)
            self.assertEqual((child.returncode, child.wait(), child.stdin.closed), (expected, expected, True))
        child = subprocess.Popen([sys.executable, "-I", "-c", "import time\ntime.sleep(600)"])
        self.addCleanup(child.kill)
        meter, started = Meter(), time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            reap(child, meter, started, 0.3)
        self.assertTrue(0.3 <= time.monotonic() - started < 10)
        self.assertEqual((child.returncode, meter.report()["max_rss_kilobytes"]), (None, None))
        child.kill(); reap(child, meter, started)
        self.assertEqual(child.returncode, -9)
        self.assertTrue(meter.report()["wall_milliseconds"] >= 300 and meter.report()["max_rss_kilobytes"] > 0, meter.report())

    def test_actual_command_line_prints_usage_and_keeps_its_exit_codes(self):
        for body, code in ((SPIN + DONE, 0), (SPIN + 'print(json.dumps({"holds": False, "summary": {}}))', 1)):
            root = Path(tempfile.mkdtemp(dir=self.root))
            core, consumer, bundle = make_program(root, source(body))
            path = root / "bundle.json"; path.write_bytes(encode(bundle))
            arguments = ["-m", "hypersearch", "run-program", "--bundle", str(path), "--consumer-root", str(consumer),
                         "--db", str(root / "tasks.sqlite"), "--export", str(root / "receipts")]
            env = {"PATH": os.defpath, "PYTHONPATH": str(core / "src")}
            result = subprocess.run([sys.executable, *launch(root / "cache-1"), *arguments], env=env,
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, code, result.stderr)
            printed = json.loads(result.stdout)
            self.assertEqual(set(printed), {"execution", "receipt_sha256", "receipt_path", "outcome_status",
                                            "replay_matches_parent", "usage"})
            self.assertTrue(printed["usage"]["cpu_milliseconds"] >= 400 and printed["usage"]["max_rss_kilobytes"] > 0, printed)
            again = subprocess.run([sys.executable, *launch(root / "cache-2"), *arguments], env=env,
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual((again.returncode, set(json.loads(again.stdout))), (code, set(printed) - {"usage"}))


if __name__ == "__main__":
    unittest.main()
