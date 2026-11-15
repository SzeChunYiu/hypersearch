"""Ignored bytecode caches must never stand in for hash-pinned source.

Source hashes bind files, not the code an interpreter loads: an ignored cache is
invisible to `git status` yet eligible for import. Fixtures are synthetic.
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

from hypersearch.study import run_verifier
from hypersearch.study_json import encode
from review_fixture import fixture
from study_fixture import git, make

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


def command(core, *arguments, flags=("-B", "-S")):
    return subprocess.run([sys.executable, *flags, "-m", "hypersearch", *map(str, arguments)],
                          env={"PATH": os.defpath, "PYTHONPATH": str(core / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=90)


class BytecodeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.marker = self.root / "marker"

    def study(self, core, consumer, bundle, name, flags=("-B", "-S")):
        source = self.root / "bundle.json"; source.write_bytes(encode(bundle))
        result = command(core, "run-study", "--bundle", source, "--consumer-root", consumer,
                         "--db", self.root / (name + ".sqlite"), "--export", self.root / name, flags=flags)
        return result, [p.name for p in (self.root / (name + ".sqlite"), self.root / name) if p.exists()]

    def test_false_witness_is_never_receipted_verified_from_cached_code(self):
        core, consumer, bundle = make(self.root, multi=True, false=True)
        result, _ = self.study(core, consumer, bundle, "clean")
        self.assertEqual((result.returncode, json.loads(result.stdout)["outcome_status"]), (1, "REFUTED_WITNESS"))
        for index, stale in enumerate((False, True)):
            poison(core, "study_outcomes", FLIP, stale=stale)
            self.assertEqual(git(core, "status", "--porcelain", "--untracked-files=all"), "")
            result, effects = self.study(core, consumer, bundle, f"poisoned-{index}")
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("bytecode cache", result.stderr)
            self.assertEqual(effects, [])
            shutil.rmtree(core / "src/hypersearch/__pycache__")
        result, _ = self.study(core, consumer, bundle, "restored")
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_private_prefix_launch_never_executes_adjacent_cache(self):
        core, consumer, bundle = make(self.root)
        for module in ("__init__", "cli", "study", "study_paths", "study_outcomes", "store"):
            poison(core, module, MARK.format(marker=str(self.marker)))
        private = self.root / "private-cache"
        result, effects = self.study(core, consumer, bundle, "hardened",
                                     flags=("-B", "-S", "-X", f"pycache_prefix={private}"))
        self.assertEqual(result.returncode, 2)       # an unclean checkout is still refused,
        self.assertIn("bytecode cache", result.stderr)
        self.assertFalse(self.marker.exists())       # and none of its cached code ever ran,
        self.assertEqual(effects, [])                # including the gate's own module.

    def test_populated_redirected_cache_is_refused(self):
        core, consumer, bundle = make(self.root)
        prefix = self.root / "shared-cache"
        poison(core, "study_outcomes", MARK.format(marker=str(self.marker)), prefix=prefix)
        result, effects = self.study(core, consumer, bundle, "redirected",
                                     flags=("-B", "-S", "-X", f"pycache_prefix={prefix}"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("redirected bytecode cache", result.stderr)
        self.assertEqual(effects, [])

    def test_review_route_refuses_cached_code_before_registration(self):
        core, consumer, value = fixture(self.root)
        poison(core, "review_contract", MARK.format(marker=str(self.marker)))
        source = self.root / "review.json"; source.write_bytes(encode(value))
        result = command(core, "register-review", "--bundle", source, "--consumer-root", consumer,
                         "--db", self.root / "reviews.sqlite", "--export", self.root / "reviews")
        self.assertEqual(result.returncode, 2)
        self.assertIn("bytecode cache", result.stderr)
        self.assertFalse((self.root / "reviews.sqlite").exists())

    def test_verifier_child_ignores_adjacent_cache(self):
        core, _, bundle = make(self.root, multi=True, false=True)
        for module in ("study_worker", "multiwise", "study_contract", "study_json"):
            poison(core, module, MARK.format(marker=str(self.marker)))
        result, diagnostics = run_verifier(bundle, core)
        self.assertEqual((result["status"], diagnostics), ("REFUTED_WITNESS", ""))
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
