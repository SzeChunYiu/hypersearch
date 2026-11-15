"""Ignored bytecode and ambient import paths must never stand in for pinned source.

Source hashes bind files, not the code an interpreter loads: an ignored cache or
a module found earlier on the import path is invisible to `git status` yet
eligible for import. Fixtures are synthetic.
"""
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hypersearch.study import run_verifier
from hypersearch.study_paths import executable_boundary
from hypersearch.study_json import encode
from review_fixture import fixture
from study_fixture import git, launch, make

TAG = sys.implementation.cache_tag
# Behaviour-preserving: proves only which bytes executed.
MARK = "\nopen({marker!r}, 'a').write(__name__ + '\\n')\n"
# Turns a completed refutation into a self-consistent verified outcome.
FLIP = '''
def verification(value, bundle):
    question, length = bundle["question"], bundle["question"]["length"]
    certificate = parse(artifact_bytes(bundle["artifacts"]["certificate"]), 65536)
    forged = {"verified": True, "scope": "finite_group_multiwise_lower_bound", "moduli": question["moduli"],
              "k": question["k"], "sequence_length": length, "maximum_disjoint_zero_sum_subsequences": 1,
              "maximal_packing_indices": [[0, 1]], "subsets_checked": (1 << length) - 1, "packing_transitions": 1,
              "certificate_sha256": digest(encode(certificate)), "formal_proof": False, "novelty_assessed": False,
              "evidence_kind": "exact_bounded_computational_verification", "lower_bound": length + 1}
    return {"status": "VERIFIED_WITNESS", "verification": forged}
'''


def poison(core, module, addition, stale=False, prefix=None):
    """Cache different code for an unchanged pinned module, as an ignored file."""
    source = core / "src/hypersearch" / (module + ".py")
    directory = (source.parent / "__pycache__" if prefix is None
                 else Path(prefix) / source.parent.relative_to(source.anchor))
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{module}.{TAG}.pyc"
    with tempfile.TemporaryDirectory() as scratch:
        changed = Path(scratch) / "changed.py"
        changed.write_text(source.read_text() + addition)
        mode = py_compile.PycInvalidationMode.TIMESTAMP if stale else py_compile.PycInvalidationMode.UNCHECKED_HASH
        py_compile.compile(str(changed), cfile=str(target), dfile=str(source), doraise=True, invalidation_mode=mode)
    if stale:  # a stale cache whose header still matches the pinned file's mtime and size
        stat, raw = source.stat(), bytearray(target.read_bytes())
        raw[8:12] = (int(stat.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little")
        raw[12:16] = (stat.st_size & 0xFFFFFFFF).to_bytes(4, "little")
        target.write_bytes(bytes(raw))


def command(core, *arguments, flags, cwd=None, path=None):
    return subprocess.run([sys.executable, *flags, "-m", "hypersearch", *map(str, arguments)],
                          env={"PATH": os.defpath, "PYTHONPATH": str(path or core / "src")},
                          cwd=cwd, capture_output=True, text=True, timeout=90)


class BytecodeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.marker = self.root / "marker"
        self.safe = launch(self.root / "private-cache")

    def study(self, core, consumer, bundle, name, flags=None, **launch_options):
        source = self.root / "bundle.json"; source.write_bytes(encode(bundle))
        result = command(core, "run-study", "--bundle", source, "--consumer-root", consumer,
                         "--db", self.root / (name + ".sqlite"), "--export", self.root / name,
                         flags=self.safe if flags is None else flags, **launch_options)
        return result, [p.name for p in (self.root / (name + ".sqlite"), self.root / name) if p.exists()]

    def refused(self, outcome, reason):
        result, effects = outcome
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertEqual(effects, [])

    def test_false_witness_is_never_receipted_verified_from_cached_code(self):
        core, consumer, bundle = make(self.root, multi=True, false=True)
        result, _ = self.study(core, consumer, bundle, "clean")
        self.assertEqual((result.returncode, json.loads(result.stdout)["outcome_status"]), (1, "REFUTED_WITNESS"))
        for index, stale in enumerate((False, True)):
            poison(core, "study_outcomes", FLIP, stale=stale)
            self.assertEqual(git(core, "status", "--porcelain", "--untracked-files=all"), "")
            # The launch that used to read this cache, and the required one, both refuse.
            self.refused(self.study(core, consumer, bundle, f"legacy-{index}", flags=("-B", "-S")), "launch with")
            self.refused(self.study(core, consumer, bundle, f"poisoned-{index}"), "bytecode cache")
            shutil.rmtree(core / "src/hypersearch/__pycache__")
        result, _ = self.study(core, consumer, bundle, "restored")
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_required_launch_never_executes_adjacent_cache(self):
        core, consumer, bundle = make(self.root)
        for module in ("__init__", "__main__", "cli", "study", "study_paths", "study_outcomes", "store"):
            poison(core, module, MARK.format(marker=str(self.marker)))
        self.refused(self.study(core, consumer, bundle, "hardened"), "bytecode cache")
        self.assertFalse(self.marker.exists())  # not even the gate's own module ran from cache

    def test_every_part_of_the_launch_contract_is_required(self):
        core, consumer, bundle = make(self.root)
        private = f"pycache_prefix={self.root / 'private-cache'}"
        for index, flags in enumerate((("-S", "-P", "-X", private), ("-B", "-P", "-X", private),
                                       ("-B", "-S", "-X", private), ("-B", "-S", "-P"))):
            self.refused(self.study(core, consumer, bundle, f"partial-{index}", flags=flags), "launch with")
            shutil.rmtree(core / "src/hypersearch/__pycache__", ignore_errors=True)  # written when -B is absent

    def test_working_directory_and_alias_paths_cannot_supply_modules(self):
        core, consumer, bundle = make(self.root, multi=True, false=True)
        cwd = self.root / "cwd"; cwd.mkdir()
        shadow = cwd / "argparse.py"   # a standard-library name in the launch directory
        shadow.write_text(f"open({str(self.marker)!r}, 'a').write('shadow')\nraise SystemExit(0)\n")
        py_compile.compile(str(shadow), cfile=str(cwd / "argparse.pyc"), doraise=True); shadow.unlink()
        result, _ = self.study(core, consumer, bundle, "shadow", cwd=cwd)
        self.assertEqual((result.returncode, self.marker.exists()), (1, False), result.stderr)
        # Launch mistakes are refused before the shadow could be imported at all.
        self.refused(self.study(core, consumer, bundle, "no-safe-path", cwd=cwd, flags=[f for f in self.safe if f != "-P"]), "launch with")
        self.refused(self.study(core, consumer, bundle, "empty-entry", cwd=cwd, path=f"{core / 'src'}:"), "import path")
        self.assertFalse(self.marker.exists())
        alias = self.root / "alias"; alias.mkdir()
        (alias / "hypersearch").symlink_to(core / "src/hypersearch", target_is_directory=True)
        self.refused(self.study(core, consumer, bundle, "alias-run", path=alias), "import path")

    def test_cache_prefix_must_be_new_and_empty(self):
        core, consumer, bundle = make(self.root)
        prefix = self.root / "shared-cache"
        poison(core, "study_outcomes", MARK.format(marker=str(self.marker)), prefix=prefix)
        self.refused(self.study(core, consumer, bundle, "redirected", flags=launch(prefix)), "new empty directory")
        unrelated = self.root / "reused-cache"; unrelated.mkdir(); (unrelated / "other.pyc").write_bytes(b"")
        self.refused(self.study(core, consumer, bundle, "reused", flags=launch(unrelated)), "new empty directory")
        # In-process callers skip the launch contract; admission still sees the redirected cache.
        tracked = set(git(core, "ls-files").splitlines())
        with patch.object(sys, "pycache_prefix", str(prefix)), self.assertRaisesRegex(ValueError, "redirected bytecode cache"):
            executable_boundary(core, tracked)

    def test_inspect_mode_cannot_rewrite_the_exit_code(self):
        core, consumer, bundle = make(self.root, multi=True, false=True)
        (core / "untracked.txt").write_text("dirty")   # a refusal, which -i would otherwise turn into exit 0
        source = self.root / "bundle.json"; source.write_bytes(encode(bundle))
        arguments = ("run-study", "--bundle", source, "--consumer-root", consumer,
                     "--db", self.root / "inspect.sqlite", "--export", self.root / "inspect")
        for flags, extra in (((*self.safe, "-i"), {}), (self.safe, {"PYTHONINSPECT": "1"})):
            result = subprocess.run([sys.executable, *flags, "-m", "hypersearch", *map(str, arguments)],
                                    env={"PATH": os.defpath, "PYTHONPATH": str(core / "src"), **extra},
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("launch without -i", result.stderr)
            self.assertFalse((self.root / "inspect.sqlite").exists())

    def test_any_entry_named_pycache_is_refused(self):
        core, consumer, bundle = make(self.root)
        cache = core / "src/hypersearch/__pycache__"
        cache.mkdir()
        self.refused(self.study(core, consumer, bundle, "empty-directory"), "bytecode cache")
        os.mkfifo(cache / f"study_outcomes.{TAG}.pyc")   # not a regular file; never opened
        self.refused(self.study(core, consumer, bundle, "pipe"), "bytecode cache")
        shutil.rmtree(cache); cache.write_text("not a directory")
        Path(core, ".git/info/exclude").write_text("__pycache__\n")
        self.refused(self.study(core, consumer, bundle, "plain-file"), "bytecode cache")

    def test_review_route_refuses_cached_code_before_registration(self):
        core, consumer, value = fixture(self.root)
        poison(core, "review_contract", MARK.format(marker=str(self.marker)))
        source = self.root / "review.json"; source.write_bytes(encode(value))
        arguments = ("register-review", "--bundle", source, "--consumer-root", consumer,
                     "--db", self.root / "reviews.sqlite", "--export", self.root / "reviews")
        for flags, reason in ((self.safe, "bytecode cache"), (("-B", "-S"), "launch with")):
            result = command(core, *arguments, flags=flags)
            self.assertEqual(result.returncode, 2)
            self.assertIn(reason, result.stderr)
            self.assertFalse((self.root / "reviews.sqlite").exists())

    def test_crash_never_exits_as_a_refutation(self):
        core, consumer, bundle = make(self.root)
        (core / "src/hypersearch/study_receipts.py").write_text("raise RuntimeError('synthetic crash')\n")
        result, effects = self.study(core, consumer, bundle, "crash")
        self.assertEqual((result.returncode, effects), (2, []), result.stderr)

    def test_verifier_child_ignores_adjacent_cache(self):
        core, _, bundle = make(self.root, multi=True, false=True)
        for module in ("study_worker", "multiwise", "study_contract", "study_json"):
            poison(core, module, MARK.format(marker=str(self.marker)))
        result, diagnostics = run_verifier(bundle, core)
        self.assertEqual((result["status"], diagnostics), ("REFUTED_WITNESS", ""))
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
