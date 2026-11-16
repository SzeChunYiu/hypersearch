"""The export check on real receipts: files, lineage and routes. Synthetic consumers only."""
import ast
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from hypersearch import export_check, program_contract as contract
from hypersearch.census import census_route
from hypersearch.export_check import check
from hypersearch.program import program_route
from hypersearch.study import study_route
from hypersearch.study_json import digest, encode, parse
from census_fixture import make_census
from export_fixture import family, forged, place, produce
from study_fixture import make

FIRST, SECOND = "fixture-first", "fixture-second"


def kinds(items):
    return [item["problem"] for item in items]


class ExportCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.family = family(Path(cls.temp.name))
        cls.all = [raw for pair in cls.family.values() for raw in pair]

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=self.temp.name))

    def report(self, *receipts, extra=()):
        return check("program", [place(self.root / "export", *receipts), *extra])

    def test_an_intact_family_is_reported_in_full_and_nothing_is_written(self):
        originals = place(self.root / "originals", *(pair[0] for pair in self.family.values()))
        replays = place(self.root / "replays", *(pair[1] for pair in self.family.values()))
        (replays / ".receipt-interrupted").write_bytes(b"half a receipt")
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        report = check("program", [str(originals), str(replays)])
        self.assertEqual({path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}, before)
        self.assertEqual(set(report), {"check", "route", "receipts", "ignored_dot_files", "studies", "problems", "ok"})
        self.assertEqual((report["check"], report["route"], report["receipts"], report["ignored_dot_files"],
                          report["problems"], report["ok"]), ("export", "program", 4, 1, [], True))
        self.assertEqual(sorted(report["studies"]), [FIRST, SECOND])
        original, replay = self.family[FIRST]
        row = {"outcome_status": "PROGRAM_HOLDS", "python": parse(original)["runtime"]["python"]}
        self.assertEqual(report["studies"][FIRST], {
            "originals": [dict(row, receipt_sha256=digest(original), elapsed_ms=parse(original)["runtime"]["elapsed_ms"])],
            "replays": [dict(row, receipt_sha256=digest(replay), elapsed_ms=parse(replay)["runtime"]["elapsed_ms"],
                             parent_receipt_sha256=digest(original), matches_parent=True)],
            "replayed": True, "problems": []})
        self.assertEqual(parse(encode(report)), report)      # readable by the package's own strict parser
        both = self.report(*self.all, extra=[originals])     # a receipt present in two directories is one receipt
        self.assertEqual((both["receipts"], both["ok"]), (4, True))

    def test_a_damaged_or_foreign_entry_is_a_problem_and_never_a_receipt(self):
        original, replay = self.family[FIRST]
        elsewhere = place(self.root / "elsewhere", original)
        tampered = bytearray(original); tampered[-2] ^= 1
        loose = json.dumps(parse(original), indent=1).encode()
        garbage = b"not a receipt"
        refrozen = parse(original); refrozen["outcome"]["verification"]["summary"]["count"] = 5
        other_version = parse(original); other_version["execution"]["bundle"]["instrument"]["release_version"] = "0.0.1"
        census = Path(tempfile.mkdtemp(dir=self.temp.name))
        foreign = produce(census_route, *make_census(census), census)[0]
        cases = {
            "tampered": (digest(original) + ".json", bytes(tampered), "file name is not the digest of its bytes"),
            "renamed": ("renamed.json", original, "file name is not the digest of its bytes"),
            "not json name": ("notes.txt", original, "not a regular .json file"),
            "garbage": (digest(garbage) + ".json", garbage, "receipt refused by the route's validator"),
            "edited then renamed": (digest(encode(refrozen)) + ".json", encode(refrozen), "receipt refused by the route's validator"),
            "loose encoding": (digest(loose) + ".json", loose, "receipt is not in the committed encoding"),
            "too large": ("large.json", b" " * (2 * 1048576 + 1), "file exceeds the receipt byte bound"),
            "another route": (digest(foreign) + ".json", foreign, "receipt belongs to another route"),
            "another version": (digest(encode(other_version)) + ".json", encode(other_version),
                                "receipt names another instrument version"),
            "symlink": (digest(original) + ".json", None, "symlink entry"),
            "directory": ("nested.json", None, "not a regular .json file"),
        }
        for label, (name, data, expected) in cases.items():
            directory = place(self.root / label.replace(" ", "-"), *self.family[SECOND], replay)
            if label == "symlink":
                os.symlink(elsewhere / name, directory / name)
            elif label == "directory":
                place(directory / name, original)            # a receipt one level down is not looked for
            else:
                (directory / name).write_bytes(data)
            report = check("program", [directory])
            self.assertEqual(report["problems"], [{"problem": expected, "subject": str(directory / name)}], label)
            self.assertEqual((report["ok"], report["receipts"]), (False, 3), label)
            # The damaged original is not counted, so its replay has lost its parent.
            self.assertEqual(kinds(report["studies"][FIRST]["problems"]), ["replay parent is absent", "study has no original"], label)
            self.assertEqual((report["studies"][FIRST]["originals"], report["studies"][FIRST]["replayed"]), ([], False), label)
            self.assertEqual(report["studies"][SECOND]["problems"], [], label)

    def test_an_empty_export_is_a_problem_and_dot_files_are_counted_not_read(self):
        empty = self.root / "empty"; empty.mkdir()
        report = check("program", [empty])
        self.assertEqual((report["ok"], report["receipts"], report["studies"]), (False, 0, {}))
        self.assertEqual(report["problems"], [{"problem": "export directory holds no receipt", "subject": str(empty)}])
        (empty / ".receipt-a1b2c3").write_bytes(self.all[0]); (empty / ".hidden.json").write_bytes(b"{}")
        report = check("program", [empty])
        self.assertEqual((report["ignored_dot_files"], kinds(report["problems"])), (2, ["export directory holds no receipt"]))
        full = place(self.root / "full", *self.all)
        report = check("program", [full, empty])
        self.assertEqual((report["ok"], report["receipts"], kinds(report["problems"])),
                         (False, 4, ["export directory holds no receipt"]))
        (self.root / "file").write_bytes(b""); os.symlink(full, self.root / "link")
        for bad in ([], [self.root / "missing"], [self.root / "file"], [self.root / "link"], [full, full],
                    [full, self.root / "full/../full"]):
            with self.assertRaises(ValueError, msg=bad):
                check("program", bad)
        with self.assertRaises(ValueError):
            check("review", [full])
        with patch("hypersearch.export_check.open", side_effect=PermissionError("denied"), create=True):
            report = check("program", [full])
        self.assertEqual((report["receipts"], set(kinds(report["problems"]))),
                         (0, {"file cannot be read", "export directory holds no receipt"}))

    def test_every_problem_string_is_documented_and_every_documented_one_exists(self):
        emitted = set()
        for node in ast.walk(ast.parse(Path(export_check.__file__).read_text())):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "problem":
                emitted |= {item.value for item in ast.walk(node.args[0]) if isinstance(item, ast.Constant)}
            elif isinstance(node, ast.FunctionDef) and node.name in ("admit", "refusal", "compare"):
                emitted |= {item.value for item in ast.walk(node)
                            if isinstance(item, ast.Constant) and item is not node.body[0].value}   # not the docstring
        emitted = {text for text in emitted if type(text) is str and " " in text}
        page = (Path(__file__).resolve().parents[1] / "docs/CHECK_EXPORT.md").read_text()
        documented = set(re.findall(r"^\| `([^`]+)` \| [a-z ]+ \| (?:top|study) \|$", page, re.M))
        self.assertEqual((emitted, len(emitted)), (documented, 23))

    def test_a_replay_is_held_against_a_present_original_of_the_same_bundle(self):
        original, replay = self.family[FIRST]
        other, other_replay = self.family[SECOND]
        report = self.report(replay, other, other_replay)
        study = report["studies"][FIRST]
        self.assertEqual(study["problems"], [{"problem": "replay parent is absent", "subject": digest(replay)},
                                             {"problem": "study has no original", "subject": FIRST}])
        self.assertEqual((study["replays"][0]["matches_parent"], study["replayed"], report["ok"]), (None, False, False))
        self.assertTrue(report["studies"][SECOND]["replayed"])
        route = program_route()
        crossed = forged(other_replay, execution=route.wrapper(parse(other)["execution"]["bundle"],
                                                               parent=digest(original), replay_id="crossed"))
        chained = forged(replay, execution=route.wrapper(parse(original)["execution"]["bundle"],
                                                         parent=digest(replay), replay_id="chained"))
        for label, extra, study_id, expected in (("another bundle", crossed, SECOND, "replay bundle differs from its parent"),
                                                 ("a replay as parent", chained, FIRST, "replay parent is not an original")):
            self.root = Path(tempfile.mkdtemp(dir=self.temp.name))
            report = self.report(*self.all, extra)
            study = report["studies"][study_id]
            self.assertEqual(study["problems"], [{"problem": expected, "subject": digest(extra)}], label)
            self.assertEqual(report["ok"], False, label)
            self.assertEqual({row["receipt_sha256"]: row["matches_parent"] for row in study["replays"]},
                             {digest(extra): None, digest(self.family[study_id][1]): True}, label)
            self.assertTrue(study["replayed"], label)        # the honest replay still counts

    def test_the_stored_replay_flag_is_recomputed_not_trusted(self):
        original, replay = self.family[FIRST]
        bundle = parse(original)["execution"]["bundle"]
        different = contract.verification(contract.record({"holds": True, "summary": {"count": 9, "note": "not registered"}}, bundle), bundle)
        for label, changes, matches, expected in (
                ("flag says no, outcomes agree", dict(replay_matches_parent=False), True,
                 ["replay flag disagrees with the recomputed comparison"]),
                ("flag says yes, outcomes differ", dict(outcome=different), False,
                 ["replay flag disagrees with the recomputed comparison", "replay does not match its parent"]),
                ("flag says no, outcomes differ", dict(outcome=different, replay_matches_parent=False), False,
                 ["replay does not match its parent"])):
            self.root = Path(tempfile.mkdtemp(dir=self.temp.name))
            changed = forged(replay, **changes)
            report = self.report(original, changed, *self.family[SECOND])
            study = report["studies"][FIRST]
            self.assertEqual(study["problems"], [{"problem": text, "subject": digest(changed)} for text in expected], label)
            self.assertEqual((study["replays"][0]["matches_parent"], study["replayed"], report["ok"]), (matches, False, False), label)

    def test_a_study_has_exactly_one_original(self):
        original, replay = self.family[FIRST]
        runtime = parse(original)["runtime"]
        second_database = forged(original, runtime=dict(runtime, elapsed_ms=runtime["elapsed_ms"] + 1))
        report = self.report(*self.all, second_database)
        study = report["studies"][FIRST]
        self.assertEqual(study["problems"], [{"problem": "study has more than one original", "subject": FIRST}])
        self.assertEqual([row["receipt_sha256"] for row in study["originals"]], sorted([digest(original), digest(second_database)]))
        self.assertEqual((report["ok"], report["receipts"], study["replayed"]), (False, 5, True))
        self.assertEqual(report["studies"][SECOND]["problems"], [])

    def test_the_other_frozen_routes_are_checked_by_their_own_validators(self):
        for name, make_route, built in (("study", study_route, make), ("census", census_route, make_census)):
            root = Path(tempfile.mkdtemp(dir=self.temp.name))
            core, consumer, bundle = built(root)
            original, replay = produce(make_route, core, consumer, bundle, root)
            status = parse(original)["outcome"]["status"]
            wanted = {"schema": "hypersearch.expected-outcomes/v1", "require_replay": True, "studies": {
                bundle["study_id"]: {"status": status, "summary_sha256": None, "unregistered_summary_fields": []}}}
            report = check(name, [place(root / "export", original, replay)], wanted)
            self.assertEqual((report["ok"], report["receipts"], report["route"]), (True, 2, name))
            study = report["studies"][bundle["study_id"]]
            self.assertEqual((study["originals"][0]["outcome_status"], study["replayed"]), (status, True))
            wanted["studies"][bundle["study_id"]]["summary_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "program route only"):
                check(name, [root / "export"], wanted)
            mixed = check("program", [root / "export"])      # and the program route refuses them
            self.assertEqual((mixed["receipts"], set(kinds(mixed["problems"]))),
                             (0, {"receipt belongs to another route", "export directory holds no receipt"}))


if __name__ == "__main__":
    unittest.main()
