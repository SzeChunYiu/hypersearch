"""An operator stops a pinned-program launch: through the real command line, with real signals. Linux."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from hypersearch import program_contract as contract
from hypersearch.store import Store
from hypersearch.study_json import encode, parse
from program_fixture import make_program
from study_fixture import launch
from test_program import source
from test_program_reaping import alive

# Writes its own and a grandchild's process id, then waits while the gate file exists (60 s at most).
WAITS = """import subprocess, time
pids = [os.getpid()]
if arguments["spawn"]:
    pids.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)  # " + arguments["marker"]]).pid)
with open(arguments["pids"] + ".part", "w") as out:
    out.write(json.dumps(pids))
os.rename(arguments["pids"] + ".part", arguments["pids"])
deadline = time.monotonic() + 60
while os.path.exists(arguments["gate"]) and time.monotonic() < deadline:
    time.sleep(0.05)
print(json.dumps({"holds": True, "summary": {}}))"""


def default_stop_signals():
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):  # a background test runner may ignore some
        signal.signal(number, signal.SIG_DFL)


def gone(pid, marker, seconds=10):
    deadline = time.monotonic() + seconds
    while alive(pid, marker) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not alive(pid, marker)


@unittest.skipUnless(sys.platform.startswith("linux"), "process groups and liveness are read from /proc")
class ProgramInterruptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def prepare(self, spawn):
        root = Path(tempfile.mkdtemp(dir=self.temp.name))
        marker = "hypersearch-interrupted-" + root.name
        arguments = {"pids": str(root / "pids.json"), "gate": str(root / "gate"), "marker": marker, "spawn": spawn}
        core, consumer, bundle = make_program(root, source(WAITS), arguments=arguments, timeout=120)
        (root / "bundle.json").write_bytes(encode(bundle))
        (root / "gate").touch()
        task_id = contract.execution_identity(contract.wrapper(bundle))[0]
        return root, core, consumer, marker, task_id

    def command(self, root, core, *arguments):
        cache = Path(tempfile.mkdtemp(dir=root)) / "cache"
        return ([sys.executable, *launch(cache), "-m", "hypersearch", *arguments],
                {"PATH": os.defpath, "PYTHONPATH": str(core / "src")})

    def start(self, root, core, consumer):
        argv, env = self.command(root, core, "run-program", "--bundle", str(root / "bundle.json"),
                                 "--consumer-root", str(consumer), "--db", str(root / "tasks.sqlite"),
                                 "--export", str(root / "receipts"))
        launcher = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    preexec_fn=default_stop_signals)
        self.addCleanup(lambda: launcher.poll() is None and launcher.kill())
        deadline = time.monotonic() + 60
        while not (root / "pids.json").exists():
            self.assertIsNone(launcher.poll(), launcher.stderr.read() if launcher.poll() is not None else "")
            self.assertLess(time.monotonic(), deadline, "the program never started")
            time.sleep(0.05)
        pids = json.loads((root / "pids.json").read_text())
        for pid in pids[1:]:
            self.addCleanup(lambda pid=pid: alive(pid, "hypersearch-interrupted-") and os.kill(pid, signal.SIGKILL))
        return launcher, pids

    def invoke(self, root, core, *arguments):
        argv, env = self.command(root, core, *arguments)
        return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)

    def relaunch(self, root, core, consumer):
        (root / "gate").unlink(missing_ok=True)
        (root / "pids.json").unlink(missing_ok=True)
        again = self.invoke(root, core, "run-program", "--bundle", str(root / "bundle.json"), "--consumer-root",
                         str(consumer), "--db", str(root / "tasks.sqlite"), "--export", str(root / "receipts"))
        self.assertEqual(again.returncode, 0, again.stderr)
        printed = json.loads(again.stdout)
        self.assertEqual((printed["execution"], printed["outcome_status"]), ("completed", "PROGRAM_HOLDS"))
        receipt = parse(Path(printed["receipt_path"]).read_bytes(), 1 << 21)
        self.assertEqual(receipt["attempt"]["fence"], 2)
        return Store.existing(root / "tasks.sqlite").snapshot()

    def test_a_stop_signal_kills_the_program_group_and_releases_the_lease(self):
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=number.name):
                root, core, consumer, marker, task_id = self.prepare(spawn=True)
                launcher, (program, grandchild) = self.start(root, core, consumer)
                self.assertTrue(alive(program, "program.py") and alive(grandchild, marker))
                launcher.send_signal(number)                       # to the launcher alone, not its group
                out, err = launcher.communicate(timeout=60)
                self.assertEqual(launcher.returncode, 2, err)
                printed = json.loads(out)
                self.assertEqual((printed["execution"], printed["signal"], printed["task_id"], printed["fence"],
                                  printed["lease_released"], printed["task_state"]),
                                 ("interrupted", number.name, task_id, 1, True, "pending"))
                self.assertTrue(gone(program, "program.py") and gone(grandchild, marker), "the program group survived")
                state = Store.existing(root / "tasks.sqlite").snapshot()
                self.assertEqual([e["kind"] for e in state["events"]], ["submitted", "acquired", "interrupted"])
                self.assertEqual(json.loads(state["events"][2]["detail"]), {"signal": number.name})
                self.assertEqual(json.loads(state["events"][1]["detail"])["holder"]["pid"], launcher.pid)
                self.assertEqual((state["results"], state["budget"]["spent"]), ([], 1))
                self.assertFalse((root / "receipts").exists())
                state = self.relaunch(root, core, consumer)        # accepted at once, as fence 2
                self.assertEqual([e["kind"] for e in state["events"]][3:], ["acquired", "completed"])
                self.assertEqual(state["budget"]["spent"], 2)      # the interrupted attempt stays charged

    def test_a_killed_launcher_takes_its_program_and_its_lease_is_abandoned_only_once_it_is_dead(self):
        root, core, consumer, marker, task_id = self.prepare(spawn=False)
        launcher, (program,) = self.start(root, core, consumer)
        abandon = ("abandon-attempt", "--db", str(root / "tasks.sqlite"), "--task", task_id, "--fence", "1",
                   "--reason", "launcher killed by its supervisor")
        before = Store.existing(root / "tasks.sqlite").snapshot()
        refused = self.invoke(root, core, *abandon)
        self.assertEqual((refused.returncode, refused.stdout), (2, ""))
        self.assertIn("still running", refused.stderr)
        for fence in ("2", "0"):
            wrong = self.invoke(root, core, *abandon[:6], fence, *abandon[7:])
            self.assertEqual(wrong.returncode, 2); self.assertIn("not the current lease", wrong.stderr)
        self.assertEqual(Store.existing(root / "tasks.sqlite").snapshot(), before)
        launcher.kill(); launcher.wait()                           # SIGKILL: no handler runs
        self.assertTrue(gone(program, "program.py"), "the program outlived its killed launcher")
        self.assertEqual(Store.existing(root / "tasks.sqlite").snapshot(), before)   # still leased
        freed = self.invoke(root, core, *abandon)
        self.assertEqual(freed.returncode, 0, freed.stderr)
        printed = json.loads(freed.stdout)
        self.assertEqual((printed["execution"], printed["task_id"], printed["fence"], printed["task_state"],
                          printed["holder"]["pid"]), ("abandoned", task_id, 1, "pending", launcher.pid))
        after = Store.existing(root / "tasks.sqlite").snapshot()
        self.assertEqual(after["events"][:len(before["events"])], before["events"])
        self.assertEqual(json.loads(after["events"][-1]["detail"])["reason"], "launcher killed by its supervisor")
        state = self.relaunch(root, core, consumer)
        self.assertEqual([e["kind"] for e in state["events"]], ["submitted", "acquired", "abandoned", "acquired", "completed"])
        self.assertEqual(state["budget"]["spent"], 2)
        again = self.invoke(root, core, *abandon)                     # completed: never reopened
        self.assertEqual(again.returncode, 2); self.assertIn("completed", again.stderr)
        self.assertEqual(Store.existing(root / "tasks.sqlite").snapshot(), state)
        self.assertEqual(len(list((root / "receipts").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
