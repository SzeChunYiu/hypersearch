"""Receipts of earlier releases whose validators are unchanged: checked by check-export, never run or replayed."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hypersearch import __version__
from hypersearch.export_check import EARLIER, check
from hypersearch.program import program_route
from hypersearch.study import study_route
from hypersearch.study_contract import READ_RELEASES
from hypersearch.study_json import digest, encode, parse
from export_fixture import expected, family, place, produce, released
from study_fixture import launch, make

FIRST = "fixture-first"
SOURCE = Path(__file__).resolve().parents[1] / "src"


class EarlierReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.family = family(Path(cls.temp.name))
        cls.old = {name: released(pair, "0.7.1") for name, pair in cls.family.items()}

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=self.temp.name))

    def test_the_earlier_releases_are_reviewed_whenever_the_version_changes(self):
        # A tripwire, not a property: a new version fails here until EARLIER has been reviewed against the
        # receipt validators of the releases it names, and extended or emptied (see docs/CHECK_EXPORT.md).
        self.assertEqual((__version__, EARLIER), ("0.9.1", frozenset({"0.7.0", "0.7.1", "0.8.0", "0.9.0"})))

    def test_receipts_written_by_an_earlier_release_are_checked_in_full(self):
        for original, replay in self.old.values():
            self.assertEqual(parse(original)["execution"]["bundle"]["instrument"]["release_version"], "0.7.1")
            with patch("hypersearch.study_contract.__version__", "0.7.1"):   # that release's validators accept them
                for raw in (original, replay):
                    program_route().trusted_receipt(raw, digest(raw))
        receipts = [raw for pair in self.old.values() for raw in pair]
        report = check("program", [place(self.root / "old", *receipts)], expected())
        self.assertEqual((report["ok"], report["receipts"], report["problems"]), (True, 4, []))
        for study in report["studies"].values():
            self.assertEqual((study["replayed"], study["replays"][0]["matches_parent"], study["problems"]), (True, True, []))
        oldest = [raw for pair in self.family.values() for raw in released(pair, "0.7.0")]
        self.assertTrue(check("program", [place(self.root / "oldest", *oldest)], expected())["ok"])
        for version in ("0.6.0", "0.8.1"):                                   # a release outside the set is not read
            pair = released(self.family[FIRST], version)
            report = check("program", [place(self.root / version, *pair)])
            self.assertEqual({item["problem"] for item in report["problems"]},
                             {"receipt names another instrument version", "export directory holds no receipt"}, version)
        self.assertEqual(READ_RELEASES.get(), frozenset())                  # reset after every receipt it read

    def test_the_verifier_routes_read_earlier_receipts_the_same_way(self):
        core, consumer, bundle = make(self.root)
        pair = released(produce(study_route, core, consumer, bundle, self.root), "0.7.0", study_route())
        report = check("study", [place(self.root / "old", *pair)])
        self.assertEqual((report["ok"], report["receipts"], report["studies"][bundle["study_id"]]["replayed"]), (True, 2, True))

    def test_an_earlier_release_is_never_run_or_replayed(self):
        original, replay = self.old[FIRST]
        route = program_route()
        with self.assertRaisesRegex(ValueError, "instrument identity"):
            route.wrapper(parse(original)["execution"]["bundle"])
        for raw in (original, replay):
            with self.assertRaisesRegex(ValueError, "instrument identity"):
                route.trusted_receipt(raw, digest(raw))
        bundle = self.root / "bundle.json"; bundle.write_bytes(encode(parse(original)["execution"]["bundle"]))
        receipt = place(self.root / "old", original) / (digest(original) + ".json")
        common = ["--consumer-root", str(self.root), "--db", str(self.root / "tasks.sqlite"), "--export", str(self.root / "out")]
        for command in (["run-program", "--bundle", str(bundle)],
                        ["replay-program", "--receipt", str(receipt), "--expected-receipt-sha256", digest(original),
                         "--replay-id", "replay-2"]):
            result = subprocess.run([sys.executable, *launch(Path(tempfile.mkdtemp(dir=self.root)) / "cache"),
                                     "-m", "hypersearch", *command, *common],
                                    env={"PATH": os.defpath, "PYTHONPATH": str(SOURCE)}, capture_output=True, text=True,
                                    timeout=120)
            self.assertEqual((result.returncode, result.stdout), (2, ""), command[0])
            self.assertIn("unsupported instrument identity", result.stderr, command[0])
        self.assertFalse((self.root / "tasks.sqlite").exists() or (self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
