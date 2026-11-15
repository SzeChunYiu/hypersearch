"""Synthetic census consumers on small groups; no research question or external data."""
from hypersearch.study_json import digest, encode
from study_fixture import git, make
from test_study_contract import artifact


def make_census(root, *, moduli=(3, 3), length=7, short_max=3, long_min=None, timeout=60):
    """A committed synthetic consumer plus the frozen census bundle that names it."""
    core, consumer, study = make(root)
    question = {"adapter": "zero-sum-census", "moduli": list(moduli), "length": length, "short_max": short_max,
                "long_min": long_min, "claim_type": "exhaustive-census",
                "assumptions_sha256": study["artifacts"]["preregistration"]["sha256"]}
    limits = {"db_max_attempts": 5, "timeout_seconds": timeout, "commit_margin_seconds": 10}
    kept = {name: study["artifacts"][name] for name in ("preregistration", "claim_record")}
    manifest = encode({"schema": "hypersearch.census-manifest/v1", "study_id": "fixture-census", "question": question,
                       "limits": limits, "artifact_sha256": {k: v["sha256"] for k, v in kept.items()}})
    (consumer / "census.json").write_bytes(manifest)
    git(consumer, "add", "."); git(consumer, "commit", "-m", "Frozen census fixture")
    instrument = dict(study["instrument"], verifier="hypersearch.zero-sum-census/v1")
    bundle = {"schema": "hypersearch.census-bundle/v1", "study_id": "fixture-census",
              "consumer": dict(study["consumer"], commit=git(consumer, "rev-parse", "HEAD")),
              "instrument": instrument, "question": question,
              "artifacts": dict(kept, study_manifest=artifact("census.json", manifest)), "limits": limits}
    assert digest(manifest) == bundle["artifacts"]["study_manifest"]["sha256"]
    return core, consumer, bundle
