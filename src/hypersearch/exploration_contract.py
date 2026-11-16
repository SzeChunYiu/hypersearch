"""Closed admission for admitted exploration tasks.

An exploration runs one hash-bound, consumer-committed program exactly as a pinned-program task
does, and records what it observed. It is a receipted log of what was tried before a protocol was
frozen. It is never evidence: the program states no answer, every record says citable false, and
no frozen route or export check accepts its receipts.
"""
from . import program_contract, study_contract, study_receipts
from .study_json import encode, fields, integer, parse, sha

VERIFIER = "hypersearch.exploration/v1"
SCHEMAS = {"hypersearch.exploration-" + name + "/v1" for name in ("manifest", "bundle", "execution", "receipt")}
STATUSES = {"EXPLORATION_RECORDED"}
MAX_OUTPUT_BYTES = program_contract.MAX_OUTPUT_BYTES
MAX_DEPTH = program_contract.MAX_DEPTH
source_text = program_contract.source_text
depth = program_contract.depth


def validate_bundle(value):
    consumer, instrument, artifacts, raw = study_contract.admit_common(
        value, "hypersearch.exploration-bundle/v1", ("study_manifest", "preregistration", "claim_record", "program"))
    if instrument["verifier"] != VERIFIER:
        raise ValueError("unsupported adapter or verifier")
    if not artifacts["program"]["path"].endswith(".py"):
        raise ValueError("program must be one Python source file")
    source_text(raw["program"])
    limits = value["limits"]
    fields(limits, "db_max_attempts timeout_seconds commit_margin_seconds memory_megabytes")
    integer(limits["db_max_attempts"], 1, 2**63 - 1)
    integer(limits["timeout_seconds"], 1, 21600)
    integer(limits["commit_margin_seconds"], 5, 60)
    integer(limits["memory_megabytes"], 64, 65536)
    question = value["question"]
    fields(question, "adapter program_sha256 arguments claim_type assumptions_sha256")
    sha(question["program_sha256"])
    if (question["adapter"] != "exploration-program" or question["claim_type"] != "exploration-log"
            or question["program_sha256"] != artifacts["program"]["sha256"]
            or question["assumptions_sha256"] != artifacts["preregistration"]["sha256"]
            or type(question["arguments"]) is not dict or depth(question["arguments"]) > MAX_DEPTH
            or len(encode(question["arguments"])) > program_contract.MAX_ARGUMENT_BYTES):
        raise ValueError("unsupported question scope")
    manifest = parse(raw["study_manifest"])
    fields(manifest, "schema study_id question limits artifact_sha256")
    if (manifest["schema"] != "hypersearch.exploration-manifest/v1" or manifest["study_id"] != value["study_id"]
            or encode(manifest["question"]) != encode(question) or encode(manifest["limits"]) != encode(limits)
            or manifest["artifact_sha256"] != {k: v["sha256"] for k, v in artifacts.items() if k != "study_manifest"}):
        raise ValueError("frozen manifest binding mismatch")
    return value


def validate_wrapper(value):
    return study_contract.validate_wrapper(value, schema="hypersearch.exploration-execution/v1", admit=validate_bundle)


def wrapper(bundle, *, parent=None, replay_id=None):
    return study_contract.wrapper(bundle, parent=parent, replay_id=replay_id,
                                  schema="hypersearch.exploration-execution/v1", admit=validate_bundle)


def execution_identity(value):
    return study_contract.execution_identity(value, prefix="exploration",
                                             namespace="hypersearch.exploration-replay-id/v1",
                                             validate=validate_wrapper)


def record(produced, bundle):
    """Wrap the program's observations with what they are not. A verdict field is refused."""
    fields(produced, "observations")
    question = bundle["question"]
    return {"scope": "consumer_exploration_output", "program_sha256": question["program_sha256"],
            "arguments": question["arguments"], "observations": produced["observations"],
            "evidence_kind": "exploration_log", "citable": False, "result_checked_by_instrument": False,
            "formal_proof": False, "novelty_assessed": False}


def verification(value, bundle):
    """Bind recorded observations to their frozen question. The observations are not checked."""
    question = bundle["question"]
    fields(value, "scope program_sha256 arguments observations evidence_kind citable result_checked_by_instrument "
                  "formal_proof novelty_assessed")
    if (value["scope"] != "consumer_exploration_output" or value["evidence_kind"] != "exploration_log"
            or value["citable"] is not False or value["result_checked_by_instrument"] is not False
            or value["formal_proof"] is not False or value["novelty_assessed"] is not False
            or value["program_sha256"] != question["program_sha256"]
            or encode(value["arguments"]) != encode(question["arguments"])):
        raise ValueError("wrong exploration task binding")
    if type(value["observations"]) is not dict:
        raise ValueError("exploration output must be an observations object")
    if depth(value["observations"]) > MAX_DEPTH:
        raise ValueError("exploration observations are nested too deeply")
    if len(encode(value["observations"])) > MAX_OUTPUT_BYTES:
        raise ValueError("exploration observations exceed admitted byte bound")
    return {"status": "EXPLORATION_RECORDED", "verification": value}


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
    return study_receipts.validate_receipt(value, schema="hypersearch.exploration-receipt/v1",
                                           validate=validate_wrapper, identity=execution_identity, judge=outcome)


def trusted_receipt(raw, expected_digest):
    return study_receipts.trusted_receipt(raw, expected_digest, validator=validate_receipt)
