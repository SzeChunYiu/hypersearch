import base64
from copy import deepcopy
import unittest

from hypersearch.lean_snapshot import SCHEMA, snapshot_digest, validate_snapshot
from hypersearch.study_json import digest


def artifact(path, raw=b"theorem demo : True := True.intro\n"):
    return {"path": path, "bytes": len(raw), "sha256": digest(raw),
            "base64": base64.b64encode(raw).decode("ascii")}


def snapshot(*items):
    return {"schema": SCHEMA, "files": list(items)}


class LeanSnapshotTests(unittest.TestCase):
    def test_exact_bytes_and_order_independent_identity(self):
        a, b = artifact("Main.lean"), artifact("lean-toolchain", b"leanprover/lean4:v4.35.0\n")
        self.assertEqual(validate_snapshot(snapshot(a, b))["Main.lean"],
                         base64.b64decode(a["base64"]))
        self.assertEqual(snapshot_digest(snapshot(a, b)), snapshot_digest(snapshot(b, a)))
        self.assertNotEqual(snapshot_digest(snapshot(a)),
                            snapshot_digest(snapshot(artifact("Main.lean", b"-- changed\n"))))

    def test_byte_binding_and_closed_fields(self):
        for field, value in (("bytes", True), ("bytes", 0), ("sha256", "0" * 64),
                             ("base64", "not base64"), ("symlink", "elsewhere")):
            bad = artifact("Main.lean")
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_snapshot(snapshot(bad))
        bad = snapshot(artifact("Main.lean"))
        bad["formal_proof"] = True
        with self.assertRaises(ValueError):
            validate_snapshot(bad)

    def test_unsafe_and_compiled_paths(self):
        for path in ("../Main.lean", "/Main.lean", "a//Main.lean", "a/./Main.lean",
                     ".git/Main.lean", ".lake/Main.lean", "Main.olean", "Main.ilean",
                     "bundle.zip", "a\\Main.lean", "a:Main.lean", "é.lean"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_snapshot(snapshot(artifact(path)))

    def test_duplicate_and_prefix_paths(self):
        for a, b in (("A.lean", "A.lean"), ("A.lean", "a.lean"),
                     ("A.lean", "A.lean/B.lean"), ("A.lean/B.lean", "A.lean")):
            with self.subTest(paths=(a, b)), self.assertRaises(ValueError):
                validate_snapshot(snapshot(artifact(a), artifact(b)))

    def test_bounds_and_text(self):
        cases = [snapshot(), snapshot(*[artifact(f"A{i}.lean") for i in range(129)]),
                 snapshot(artifact("A.lean", b"x" * 262145)),
                 snapshot(*[artifact(f"A{i}.lean", b"x" * 262144) for i in range(5)])]
        cases += [snapshot(artifact("A.lean", raw)) for raw in (b"\xff", b"\x00", b"a\r\nb")]
        for bad in cases:
            with self.assertRaises(ValueError):
                validate_snapshot(bad)

    def test_validation_does_not_modify_input_or_certify(self):
        value = snapshot(artifact("Main.lean", b"-- no proof at all\n"))
        before = deepcopy(value)
        self.assertEqual(set(validate_snapshot(value)), {"Main.lean"})
        self.assertEqual(value, before)


if __name__ == "__main__":
    unittest.main()
