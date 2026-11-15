"""Closed admission for frozen consumer-program tasks.

One hash-bound, consumer-committed program is run in isolation and its small
JSON output is recorded. The instrument checks identity, bounds and replay
determinism. It does not check that the program is correct.
"""
from . import study_contract, study_receipts
from .study_json import encode, fields, integer, parse, sha

VERIFIER = "hypersearch.pinned-program/v1"
SCHEMAS = {"hypersearch.program-" + name + "/v1" for name in ("manifest", "bundle", "execution", "receipt")}
STATUSES = {"PROGRAM_HOLDS", "PROGRAM_FAILS"}
MAX_OUTPUT_BYTES = 65536
MAX_ARGUMENT_BYTES = 4096
MAX_DEPTH = 16


def source_text(raw):
    """Admit plain source only: strict UTF-8, tabs, newlines and printable characters.

    An archive or compiled file under a .py name contains control bytes and is refused here,
    so what a reviewer reads in the committed file is what runs.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("program must be UTF-8 source text") from error
    if not text.strip() or any((ord(c) < 32 and c not in "\t\n") or ord(c) == 127 for c in text):
        raise ValueError("program must be nonempty source text without control characters")
    return text


def depth(value):
    """Nesting depth of a parsed JSON value, without recursion."""
    deepest, pending = 0, [(value, 1)]
    while pending:
        item, level = pending.pop()
        deepest = max(deepest, level)
        if type(item) in (list, dict):
            pending.extend((child, level + 1) for child in (item.values() if type(item) is dict else item))
    return deepest


def validate_bundle(value):
    consumer, instrument, artifacts, raw = study_contract.admit_common(
        value, "hypersearch.program-bundle/v1", ("study_manifest", "preregistration", "claim_record", "program"))
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
    if (question["adapter"] != "pinned-program" or question["claim_type"] != "program-output"
            or question["program_sha256"] != artifacts["program"]["sha256"]
            or question["assumptions_sha256"] != artifacts["preregistration"]["sha256"]
            or type(question["arguments"]) is not dict or depth(question["arguments"]) > MAX_DEPTH
            or len(encode(question["arguments"])) > MAX_ARGUMENT_BYTES):
        raise ValueError("unsupported question scope")
    manifest = parse(raw["study_manifest"])
    fields(manifest, "schema study_id question limits artifact_sha256")
    if (manifest["schema"] != "hypersearch.program-manifest/v1" or manifest["study_id"] != value["study_id"]
            or encode(manifest["question"]) != encode(question) or encode(manifest["limits"]) != encode(limits)
            or manifest["artifact_sha256"] != {k: v["sha256"] for k, v in artifacts.items() if k != "study_manifest"}):
        raise ValueError("frozen manifest binding mismatch")
    return value


def validate_wrapper(value):
    return study_contract.validate_wrapper(value, schema="hypersearch.program-execution/v1", admit=validate_bundle)


def wrapper(bundle, *, parent=None, replay_id=None):
    return study_contract.wrapper(bundle, parent=parent, replay_id=replay_id,
                                  schema="hypersearch.program-execution/v1", admit=validate_bundle)


def execution_identity(value):
    return study_contract.execution_identity(value, prefix="program", namespace="hypersearch.program-replay-id/v1",
                                             validate=validate_wrapper)


def record(produced, bundle):
    """Wrap the program's own output with what it is and is not."""
    fields(produced, "holds summary")
    question = bundle["question"]
    return {"scope": "consumer_program_output", "program_sha256": question["program_sha256"],
            "arguments": question["arguments"], "holds": produced["holds"], "summary": produced["summary"],
            "evidence_kind": "pinned_program_output", "result_checked_by_instrument": False,
            "formal_proof": False, "novelty_assessed": False}


def verification(value, bundle):
    """Bind a recorded program output to its frozen question. The output itself is not checked."""
    question = bundle["question"]
    fields(value, "scope program_sha256 arguments holds summary evidence_kind result_checked_by_instrument "
                  "formal_proof novelty_assessed")
    if (value["scope"] != "consumer_program_output" or value["evidence_kind"] != "pinned_program_output"
            or value["result_checked_by_instrument"] is not False or value["formal_proof"] is not False
            or value["novelty_assessed"] is not False or value["program_sha256"] != question["program_sha256"]
            or encode(value["arguments"]) != encode(question["arguments"])):
        raise ValueError("wrong program task binding")
    if type(value["holds"]) is not bool or type(value["summary"]) is not dict:
        raise ValueError("program output must be a truth value and a summary object")
    if depth(value["summary"]) > MAX_DEPTH:  # deeper values can exhaust the encoder's recursion after the run
        raise ValueError("program summary is nested too deeply")
    if len(encode(value["summary"])) > MAX_OUTPUT_BYTES:
        raise ValueError("program summary exceeds admitted byte bound")
    return {"status": "PROGRAM_HOLDS" if value["holds"] else "PROGRAM_FAILS", "verification": value}


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
    return study_receipts.validate_receipt(value, schema="hypersearch.program-receipt/v1", validate=validate_wrapper,
                                           identity=execution_identity, judge=outcome)


def trusted_receipt(raw, expected_digest):
    return study_receipts.trusted_receipt(raw, expected_digest, validator=validate_receipt)
