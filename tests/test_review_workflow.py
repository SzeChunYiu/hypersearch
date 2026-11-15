import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from hypersearch import review_workflow as flow, review_contract as contract
from hypersearch.store import Store, StaleLease
from hypersearch.study_json import encode, parse, digest
from review_fixture import fixture, report


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core, self.consumer, self.value = fixture(self.root)
        self.patch = patch.object(flow, "CORE_ROOT", self.core); self.patch.start(); self.addCleanup(self.patch.stop)
        self.kw = dict(consumer_root=self.consumer, database=self.root/"state.sqlite", export=self.root/"exports")

    def start(self):
        flow.register(self.value, **self.kw)
        return flow.grant(self.value, **self.kw)

    def snapshot(self):
        return Store(self.kw["database"], 5).snapshot()

    def test_original_negative_duplicate_and_recovery(self):
        token = self.start()
        result = flow.submit(self.value, token, report(self.value, token), **self.kw)
        raw = Path(result["receipt_path"]).read_bytes()
        receipt = parse(raw, 3145728)
        self.assertEqual(receipt["report"]["outcome"], "objects")
        self.assertEqual(receipt["verification"], "NOT_FORMALLY_VERIFIED")
        self.assertEqual(receipt["claim_authority"], "none")
        before = self.snapshot()
        with self.assertRaises(StaleLease):
            flow.submit(self.value, token, report(self.value, token), **self.kw)
        Path(result["receipt_path"]).unlink()
        self.assertEqual(flow.recover(self.value, **self.kw)["receipt_sha256"], digest(raw))
        self.assertEqual(before, self.snapshot())

    def test_bad_report_and_forged_grant_no_effects(self):
        token = self.start(); before = self.snapshot()
        bad = report(self.value, token); bad["bundle_sha256"] = "0"*64
        with self.assertRaises(ValueError): flow.submit(self.value, token, bad, **self.kw)
        forged = dict(token, fence=token["fence"]+1)
        with self.assertRaises(StaleLease): flow.submit(self.value, forged, report(self.value, forged), **self.kw)
        self.assertEqual(before, self.snapshot()); self.assertFalse(self.kw["export"].exists())

    def test_expired_and_reclaimed_lease_charged(self):
        token = self.start()
        with patch("hypersearch.store.Store._now", return_value=float(token["expires_at"])+1):
            before = self.snapshot()
            with self.assertRaises(StaleLease): flow.submit(self.value, token, report(self.value, token), **self.kw)
            self.assertEqual(before, self.snapshot())
            newer = flow.grant(self.value, **self.kw)
            self.assertEqual(newer["fence"], 2)
            with self.assertRaises(StaleLease): flow.submit(self.value, token, report(self.value, token), **self.kw)
        self.assertEqual(self.snapshot()["budget"]["spent"], 2)

    def test_invalid_source_role_before_database(self):
        for change in ("role", "hash", "version"):
            value = copy.deepcopy(self.value)
            if change == "role": value["exclusions"].append("reviewer-b")
            if change == "hash": value["instrument"]["source_sha256"]["src/hypersearch/store.py"] = "0"*64
            if change == "version": value["instrument"]["release_version"] = "0.3.0"
            with self.assertRaises(ValueError): flow.register(value, **self.kw)
            self.assertFalse(self.kw["database"].exists())

    def test_changed_identity_and_exact_acquisition(self):
        flow.register(self.value, **self.kw)
        store = Store(self.kw["database"], 5); store.submit("aaa-unrelated", {"unrelated": True})
        changed = dict(self.value, question="Changed")
        before = self.snapshot()
        with self.assertRaises(ValueError): flow.register(changed, **self.kw)
        self.assertEqual(before, self.snapshot())
        flow.grant(self.value, **self.kw)
        self.assertEqual(self.snapshot()["tasks"][0]["state"], "pending")

    def test_parent_digest_and_receipt_corruption(self):
        token = self.start(); result = flow.submit(self.value, token, report(self.value, token), **self.kw)
        raw = Path(result["receipt_path"]).read_bytes()
        child = dict(self.value, review_id="child", parent={"task_id": token["task_id"], "receipt_sha256": digest(raw)})
        before = self.snapshot()
        with self.assertRaises(ValueError): flow.register(child, parent_raw=raw+b" ", **self.kw)
        self.assertEqual(before, self.snapshot())
        flow.register(child, parent_raw=raw, **self.kw)
        with sqlite3.connect(self.kw["database"]) as db:
            db.execute("UPDATE results SET fence=77")
        with self.assertRaises(ValueError): flow.recover(self.value, **self.kw)

    def test_strict_json_and_types(self):
        with self.assertRaises(ValueError): parse(b"{\"x\":1,\"x\":2}")
        value = copy.deepcopy(self.value); value["limits"]["lease_seconds"] = True
        with self.assertRaises(ValueError): flow.register(value, **self.kw)
        self.assertFalse(self.kw["database"].exists())

    def test_supports_never_claim_authority(self):
        for outcome in ("supports", "inconclusive", "failed", "incomplete"):
            value = dict(self.value, review_id=outcome)
            flow.register(value, **self.kw); token = flow.grant(value, **self.kw)
            result = flow.submit(value, token, report(value, token, outcome), **self.kw)
            receipt = json.loads(Path(result["receipt_path"]).read_text())
            self.assertEqual(receipt["claim_authority"], "none")
            self.assertEqual(receipt["report"]["outcome"], outcome)
