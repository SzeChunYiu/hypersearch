"""Public synthetic reports; no research or external agents executed."""
import base64
from hypersearch import __version__
from hypersearch import review_contract as contract
from hypersearch.study_json import digest, encode
from study_fixture import make


def artifact(path, data):
    return {"path": path, "bytes": len(data), "sha256": digest(data),
            "base64": base64.b64encode(data).decode()}


def fixture(root):
    core, consumer, study = make(root)
    instrument = {k:v for k,v in study["instrument"].items() if k != "verifier"}
    instrument["release_version"] = __version__
    value = {"schema": contract.BUNDLE, "review_id": "synthetic-review", "question": "Assess the frozen synthetic note",
             "role": "hostile-reviewer", "reviewer": "reviewer-b", "lineage": ["reviewer-b", "orchestrator-b"],
             "exclusions": ["author-a", "orchestrator-a"], "parent": None,
             "consumer": {k:study["consumer"][k] for k in ("repository", "commit")},
             "instrument": instrument, "artifacts": study["artifacts"], "protocol": "preregistration",
             "limits": {"db_max_attempts": 5, "lease_seconds": 300}}
    return core, consumer, value


def report(value, token, outcome="objects"):
    return {"schema": contract.REPORT, "task_id": contract.identity(value), "bundle_sha256": digest(encode(value)),
            "grant_sha256": digest(encode(token)), "reviewer": value["reviewer"], "role": value["role"],
            "outcome": outcome, "findings_kind": "author_provided_not_independently_established",
            "report": artifact("report.txt", b"Synthetic objection; not a mathematical result."), "evidence": []}
