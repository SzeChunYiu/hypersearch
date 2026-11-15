"""Closed admission for frozen exhaustive-census tasks; reuses the study wrapper and receipt shapes."""
from . import study_contract, study_receipts
from .census_verifier import VERIFIER, offending_subsequence, validate_question
from .study_json import encode, fields, integer, parse

SCHEMAS = {"hypersearch.census-" + name + "/v1" for name in ("manifest", "bundle", "execution", "receipt")}
STATUSES = {"CENSUS_EMPTY", "CENSUS_NONEMPTY"}


def validate_bundle(value):
    consumer, instrument, artifacts, raw = study_contract.admit_common(
        value, "hypersearch.census-bundle/v1", ("study_manifest", "preregistration", "claim_record"))
    if instrument["verifier"] != VERIFIER:
        raise ValueError("unsupported adapter or verifier")
    limits = value["limits"]
    fields(limits, "db_max_attempts timeout_seconds commit_margin_seconds")
    integer(limits["db_max_attempts"], 1, 2**63 - 1)
    integer(limits["timeout_seconds"], 1, 3600)
    integer(limits["commit_margin_seconds"], 1, 60)
    question = value["question"]
    fields(question, "adapter moduli length short_max long_min claim_type assumptions_sha256")
    if (question["adapter"] != "zero-sum-census" or question["claim_type"] != "exhaustive-census"
            or question["assumptions_sha256"] != artifacts["preregistration"]["sha256"]):
        raise ValueError("unsupported question scope")
    validate_question({k: question[k] for k in ("moduli", "length", "short_max", "long_min")})
    manifest = parse(raw["study_manifest"])
    fields(manifest, "schema study_id question limits artifact_sha256")
    if (manifest["schema"] != "hypersearch.census-manifest/v1" or manifest["study_id"] != value["study_id"]
            or encode(manifest["question"]) != encode(question) or encode(manifest["limits"]) != encode(limits)
            or manifest["artifact_sha256"] != {k: v["sha256"] for k, v in artifacts.items() if k != "study_manifest"}):
        raise ValueError("frozen manifest binding mismatch")
    return value


def validate_wrapper(value):
    return study_contract.validate_wrapper(value, schema="hypersearch.census-execution/v1", admit=validate_bundle)


def wrapper(bundle, *, parent=None, replay_id=None):
    return study_contract.wrapper(bundle, parent=parent, replay_id=replay_id,
                                  schema="hypersearch.census-execution/v1", admit=validate_bundle)


def execution_identity(value):
    return study_contract.execution_identity(value, prefix="census", namespace="hypersearch.census-replay-id/v1",
                                             validate=validate_wrapper)


def verification(value, bundle):
    """Check a completed census result against its frozen question; recheck any example independently."""
    question = bundle["question"]
    fields(value, "scope moduli length short_max long_min count levels example evidence_kind formal_proof novelty_assessed")
    length = question["length"]
    if (value["scope"] != "finite_group_zero_sum_census" or value["evidence_kind"] != "exhaustive_bounded_enumeration"
            or value["formal_proof"] is not False or value["novelty_assessed"] is not False
            or encode({k: value[k] for k in ("moduli", "length", "short_max", "long_min")})
            != encode({k: question[k] for k in ("moduli", "length", "short_max", "long_min")})):
        raise ValueError("wrong census task binding")
    levels, count, example = value["levels"], value["count"], value["example"]
    if type(levels) is not list or len(levels) != length + 1 or any(type(n) is not int or n < 0 for n in levels):
        raise ValueError("malformed census level profile")
    integer(count, 0, levels[-1])
    if levels[0] != 1 or (question["long_min"] is None and count != levels[-1]):
        raise ValueError("inconsistent census counts")
    if any(levels[d] == 0 and levels[d + 1] for d in range(length)):
        raise ValueError("census profile is not inherited")
    if (count == 0) != (example is None):
        raise ValueError("census example does not match its count")
    if example is not None:
        moduli = question["moduli"]
        if (type(example) is not list or len(example) != length
                or any(type(term) is not list or len(term) != len(moduli)
                       or any(type(x) is not int or not 0 <= x < n for x, n in zip(term, moduli)) for term in example)):
            raise ValueError("malformed census example")
        if offending_subsequence(example, moduli, question["short_max"], question["long_min"]) is not None:
            raise ValueError("census example contains a forbidden zero-sum")
    return {"status": "CENSUS_EMPTY" if count == 0 else "CENSUS_NONEMPTY", "verification": value}


def outcome(value, bundle):
    fields(value, "status verification")
    if type(value["status"]) is not str:
        raise ValueError("invalid outcome status")
    if value["status"] in STATUSES:
        if verification(value["verification"], bundle) != value:
            raise ValueError("inconsistent outcome status")
    elif value["status"] not in {"EXECUTION_FAILED", "INCOMPLETE"} or value["verification"] is not None:
        raise ValueError("unsupported execution outcome")
    return value


def validate_receipt(value):
    return study_receipts.validate_receipt(value, schema="hypersearch.census-receipt/v1", validate=validate_wrapper,
                                           identity=execution_identity, judge=outcome)


def trusted_receipt(raw, expected_digest):
    return study_receipts.trusted_receipt(raw, expected_digest, validator=validate_receipt)
