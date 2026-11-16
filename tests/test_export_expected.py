"""The export check against a consumer's expected outcomes, and its command line. Synthetic consumers only."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from hypersearch.export_check import check
from hypersearch.study_json import MAX_BUNDLE_BYTES, digest, encode
from export_fixture import expected, family, forged, place
from study_fixture import launch

FIRST, SECOND = "fixture-first", "fixture-second"
SOURCE = Path(__file__).resolve().parents[1] / "src"


class ExpectedOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.family = family(Path(cls.temp.name))
        cls.all = [raw for pair in cls.family.values() for raw in pair]
        cls.export = place(Path(cls.temp.name) / "export", *cls.all)

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=self.temp.name))

    def problems(self, wanted, directory=None):
        report = check("program", [directory or self.export], wanted)
        found = [(item["problem"], item["subject"]) for item in report["problems"]]
        for study in report["studies"].values():
            found += [(item["problem"], item["subject"]) for item in study["problems"]]
        self.assertEqual(report["ok"], not found)
        return found

    def test_registered_outcomes_are_met_or_each_difference_is_named(self):
        self.assertEqual(self.problems(expected()), [])
        first, second = (digest(self.family[name][0]) for name in (FIRST, SECOND))
        entry = expected()["studies"][FIRST]
        absent = dict(entry, status="PROGRAM_FAILS", summary_sha256=None, unregistered_summary_fields=[])
        self.assertEqual(self.problems(expected(change={"fixture-third": absent})), [("expected study is absent", "fixture-third")])
        unlisted = expected(); del unlisted["studies"][SECOND]
        self.assertEqual(self.problems(unlisted), [("study is not listed in the expected outcomes", SECOND)])
        self.assertEqual(self.problems(expected(change={FIRST: dict(entry, status="PROGRAM_FAILS")})),
                         [("outcome status differs from the expected status", first)])
        self.assertEqual(self.problems(expected(change={FIRST: dict(entry, status="INCOMPLETE", summary_sha256="0" * 64)})),
                         [("outcome status differs from the expected status", first),
                          ("summary digest differs from the expected digest", first)])

    def test_the_summary_digest_covers_exactly_the_registered_fields(self):
        first = digest(self.family[FIRST][0])
        entry = expected()["studies"][FIRST]
        whole = digest(encode({"count": 1, "note": "not registered"}))
        mismatch = [("summary digest differs from the expected digest", first)]
        for label, change, found in (
                ("the registered field alone, the other declared unregistered", {}, []),
                ("the whole summary, nothing unregistered", dict(summary_sha256=whole, unregistered_summary_fields=[]), []),
                ("an absent unregistered field changes nothing", dict(unregistered_summary_fields=["note", "absent"]), []),
                ("no digest registered: the summary is not compared", dict(summary_sha256=None, unregistered_summary_fields=[]), []),
                ("the registered field alone, but nothing declared unregistered", dict(unregistered_summary_fields=[]), mismatch),
                ("the whole summary, but a field declared unregistered", dict(summary_sha256=whole), mismatch),
                ("a different registered value", dict(summary_sha256=digest(encode({"count": 2}))), mismatch),
                ("the digest of the other study", dict(summary_sha256=expected()["studies"][SECOND]["summary_sha256"]), mismatch)):
            self.assertEqual(self.problems(expected(change={FIRST: dict(entry, **change)})), found, label)
        failed = forged(self.family[FIRST][0], outcome={"status": "EXECUTION_FAILED", "verification": None})
        lost = place(self.root / "failed", failed, *self.family[SECOND])
        self.assertEqual(self.problems(expected(require_replay=False), lost),
                         [("outcome status differs from the expected status", digest(failed)),
                          ("summary digest differs from the expected digest", digest(failed))])

    def test_a_required_replay_must_be_present_and_must_match(self):
        original, replay = self.family[FIRST]
        alone = place(self.root / "alone", original, *self.family[SECOND])
        self.assertEqual(self.problems(expected(), alone), [("study has no matching replay", FIRST)])
        self.assertEqual(self.problems(expected(require_replay=False), alone), [])
        report = check("program", [alone], expected(require_replay=False))
        self.assertEqual((report["studies"][FIRST]["replayed"], report["studies"][SECOND]["replayed"]), (False, True))
        disowned = forged(replay, replay_matches_parent=False)
        unsound = place(self.root / "unsound", original, disowned, *self.family[SECOND])
        self.assertEqual(self.problems(expected(), unsound),
                         [("replay flag disagrees with the recomputed comparison", digest(disowned)),
                          ("study has no matching replay", FIRST)])
        self.assertEqual(self.problems(expected(require_replay=False), unsound),
                         [("replay flag disagrees with the recomputed comparison", digest(disowned))])

    def test_the_expected_file_is_closed(self):
        entry = expected()["studies"][FIRST]
        def study(**change):
            return expected(change={FIRST: dict(entry, **change)})
        dropped = expected(); del dropped["studies"][FIRST]["status"]
        cases = [dict(expected(), extra=1), dict(expected(), schema="hypersearch.expected-outcomes/v2"),
                 dict(expected(), require_replay=1), dict(expected(), require_replay=None), dict(expected(), studies={}),
                 dict(expected(), studies=[entry]), {k: v for k, v in expected().items() if k != "require_replay"},
                 [expected()], dropped, expected(change={" ": entry}), expected(change={"x" * 257: entry}),
                 expected(change={FIRST: [entry]}), study(extra=1), study(status="VERIFIED_WITNESS"), study(status="program_holds"),
                 study(status=True), study(status=None), study(summary_sha256="0" * 63), study(summary_sha256="A" * 64),
                 study(summary_sha256=0), study(unregistered_summary_fields="note"), study(unregistered_summary_fields=None),
                 study(unregistered_summary_fields=["note", "note"]), study(unregistered_summary_fields=[1]),
                 study(unregistered_summary_fields=[""]), study(unregistered_summary_fields=[str(n) for n in range(65)]),
                 study(summary_sha256=None)]            # unregistered fields without a digest
        for bad in cases:
            with self.assertRaises(ValueError, msg=bad):
                check("program", [self.export], copy.deepcopy(bad))
        for status in ("PROGRAM_HOLDS", "PROGRAM_FAILS", "EXECUTION_FAILED", "INCOMPLETE"):
            check("program", [self.export], study(status=status))
        check("program", [self.export], study(unregistered_summary_fields=[str(n) for n in range(64)]))

    def command(self, *arguments, flags=None):
        return subprocess.run([sys.executable, *(flags or launch(Path(tempfile.mkdtemp(dir=self.root)) / "cache")),
                               "-m", "hypersearch", "check-export", *map(str, arguments)],
                              env={"PATH": os.defpath, "PYTHONPATH": str(SOURCE)}, capture_output=True, text=True, timeout=120)

    def test_actual_command_line_exit_codes_and_launch_contract(self):
        wanted = self.root / "expected.json"; wanted.write_bytes(encode(expected()))
        before = sorted(path.name for path in self.export.iterdir())
        result = self.command("--route", "program", "--export", self.export, "--expected", wanted)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        report = json.loads(result.stdout)
        self.assertEqual((report["ok"], report["receipts"], report["expected_sha256"]), (True, 4, digest(wanted.read_bytes())))
        self.assertEqual(result.stdout.strip().encode(), encode(report))    # the committed encoding, like the other commands
        bare = json.loads(self.command("--route", "program", "--export", self.export).stdout)
        self.assertEqual((bare["ok"], bare["expected_sha256"]), (True, None))
        self.assertEqual(sorted(path.name for path in self.export.iterdir()), before)
        halves = [place(self.root / "originals", *(pair[0] for pair in self.family.values())),
                  place(self.root / "replays", *(pair[1] for pair in self.family.values()))]
        result = self.command("--route", "program", "--export", halves[0], "--export", halves[1], "--expected", wanted)
        self.assertEqual((result.returncode, json.loads(result.stdout)["receipts"]), (0, 4))
        result = self.command("--route", "program", "--export", halves[0], "--expected", wanted)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual((report["ok"], [study["problems"][0]["problem"] for study in report["studies"].values()]),
                         (False, ["study has no matching replay"] * 2))
        (halves[1] / "notes.txt").write_text("left behind")
        result = self.command("--route", "program", "--export", halves[0], "--export", halves[1])
        self.assertEqual((result.returncode, json.loads(result.stdout)["problems"]),
                         (1, [{"problem": "not a regular .json file", "subject": str(halves[1] / "notes.txt")}]))
        edge = self.root / "edge.json"; edge.write_bytes(encode(expected()).ljust(MAX_BUNDLE_BYTES))   # at the bound
        self.assertEqual(self.command("--route", "program", "--export", self.export, "--expected", edge).returncode, 0)
        large = self.root / "large.json"; large.write_bytes(edge.read_bytes() + b" ")                    # one byte over
        null = self.root / "null.json"; null.write_bytes(b"null")              # malformed, never "no expected file"
        wanted.write_bytes(encode(dict(expected(), extra=1)))
        loose = self.root / "loose.json"; loose.write_text('{"schema": "hypersearch.expected-outcomes/v1", "schema": 1}')
        for refused in (("--route", "program", "--export", self.export, "--expected", wanted),
                        ("--route", "program", "--export", self.export, "--expected", loose),
                        ("--route", "program", "--export", self.export, "--expected", large),
                        ("--route", "program", "--export", self.export, "--expected", null),
                        ("--route", "program", "--export", self.export, "--expected", self.root / "missing.json"),
                        ("--route", "program", "--export", self.root / "missing"),
                        ("--route", "program", "--export", self.export, "--export", self.export),
                        ("--route", "review", "--export", self.export), ("--export", self.export), ("--route", "program")):
            result = self.command(*refused)
            self.assertEqual((result.returncode, result.stdout), (2, ""), refused)
            self.assertTrue(result.stderr, refused)
        result = self.command("--route", "program", "--export", self.export, flags=["-B", "-S"])
        self.assertEqual((result.returncode, result.stdout), (2, "")); self.assertIn("launch with", result.stderr)
        used = self.root / "used-cache"; used.mkdir(); (used / "stale.pyc").write_bytes(b"")
        result = self.command("--route", "program", "--export", self.export, flags=launch(used))
        self.assertEqual((result.returncode, result.stdout), (2, "")); self.assertIn("new empty directory", result.stderr)
        gone = self.root / "gone"; gone.mkdir()             # refused before the package's own imports, like the run commands
        line = " ".join([sys.executable, *launch(self.root / "gone-cache"), "-m", "hypersearch", "check-export",
                         "--route", "program", "--export", str(self.export)])
        result = subprocess.run(["/bin/sh", "-c", f"cd {gone} && rmdir {gone} && exec {line}"],
                                env={"PATH": os.defpath, "PYTHONPATH": str(SOURCE)}, capture_output=True, text=True, timeout=120)
        self.assertEqual((result.returncode, result.stdout), (2, "")); self.assertIn("working directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
