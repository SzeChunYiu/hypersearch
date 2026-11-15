from hypersearch import __version__
import base64
import copy
import unittest

from hypersearch.math_adapter import search
from hypersearch.study_contract import digest, encode, parse, validate_bundle, wrapper


def artifact(path, data):
    return {"path": path, "bytes": len(data), "sha256": digest(data),
            "base64": base64.b64encode(data).decode("ascii")}


def bundle(multi=False, false=False):
    certificate = ({"schema": "hypersearch.multiwise-certificate/v1", "moduli": [2],
                    "k": 2, "sequence": [[1]] * (4 if false else 3)}
                   if multi else search([2, 2, 2], max_steps=1000))
    artifacts = {"preregistration": artifact("PREREG.md", b"Known-answer conformance only.\n"),
                 "claim_record": artifact("claim.json", encode({"id": "fixture-claim"})),
                 "certificate": artifact("certificate.json", encode(certificate))}
    question = {"adapter": "multiwise-witness" if multi else "ordinary-witness",
                "moduli": [2] if multi else [2, 2, 2], "k": 2 if multi else 1,
                "length": len(certificate["sequence"]), "claim_type": "lower-bound-witness",
                "intended_bound": len(certificate["sequence"]) + 1,
                "assumptions_sha256": artifacts["preregistration"]["sha256"]}
    limits = {"db_max_attempts": 5, "timeout_seconds": 30, "commit_margin_seconds": 10,
              "max_certificate_bytes": 65536}
    manifest = {"schema": "hypersearch.study-manifest/v1", "study_id": "fixture-study",
                "question": question, "limits": limits,
                "artifact_sha256": {k: v["sha256"] for k, v in artifacts.items()}}
    artifacts["study_manifest"] = artifact("study.json", encode(manifest))
    return {"schema": "hypersearch.study-bundle/v1", "study_id": "fixture-study",
            "consumer": {"repository": "https://example.invalid/fixture", "commit": "a" * 40,
                         "claim_id": "fixture-claim", "claim_record_sha256": artifacts["claim_record"]["sha256"],
                         "preregistration_sha256": artifacts["preregistration"]["sha256"],
                         "entrypoint": "entry.py", "entrypoint_sha256": digest(b"# fixture\n")},
            "instrument": {"repository": "https://github.com/SzeChunYiu/hypersearch.git",
                           "commit": "b" * 40, "release_version": __version__, "api": "hypersearch.api/v1",
                           "verifier": "hypersearch.multiwise-subsets/v1" if multi else "hypersearch.zero-sum-subsets/v1",
                           "source_sha256": {"src/hypersearch/cli.py": "c" * 64}},
            "question": question, "artifacts": artifacts, "limits": limits}


class ContractTests(unittest.TestCase):
    def test_valid_bounded_bundles_and_false_witness_are_admissible(self):
        for value in (bundle(), bundle(True), bundle(True, True)):
            self.assertEqual(validate_bundle(value), value)

    def test_duplicate_keys_and_nonfinite_json_refused(self):
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(ValueError):
                parse(data)

    def test_modified_artifact_wrong_task_and_manifest_override_refused(self):
        cases = []
        bad = bundle(); bad["artifacts"]["certificate"]["sha256"] = "0" * 64; cases.append(bad)
        bad = bundle(); bad["question"]["moduli"] = [3]; cases.append(bad)
        bad = bundle(True); bad["question"]["k"] = 1; cases.append(bad)
        bad = bundle(); bad["question"]["claim_type"] = "upper-bound"; cases.append(bad)
        bad = bundle(); bad["limits"]["timeout_seconds"] = True; cases.append(bad)
        bad = bundle(); bad["artifacts"]["certificate"]["path"] = "../outside"; cases.append(bad)
        bad = bundle(); bad["unexpected"] = 1; cases.append(bad)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_bundle(value)

    def test_manifest_boolean_cannot_alias_a_frozen_integer(self):
        for section, key in (("question", "k"), ("limits", "commit_margin_seconds")):
            value = bundle()
            if section == "limits":
                value[section][key] = 1
            manifest = parse(base64.b64decode(value["artifacts"]["study_manifest"]["base64"]))
            manifest[section][key] = True
            value["artifacts"]["study_manifest"] = artifact("study.json", encode(manifest))
            with self.subTest(section=section), self.assertRaises(ValueError):
                validate_bundle(value)

    def test_closed_original_and_replay_wrapper_identity(self):
        value = bundle()
        original = wrapper(value)
        replay = wrapper(value, parent="d" * 64, replay_id="replay-1")
        self.assertNotEqual(digest(encode(original)), digest(encode(replay)))
        for parent, replay_id in ((None, "x"), ("d" * 64, None), ("bad", "x")):
            with self.assertRaises(ValueError):
                wrapper(value, parent=parent, replay_id=replay_id)
