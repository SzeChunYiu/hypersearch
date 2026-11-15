"""Committed receipt validation and recoverable no-overwrite exports."""
import os
from pathlib import Path
import tempfile

from .study_contract import execution_identity, validate_wrapper
from .study_json import MAX_RECEIPT_BYTES, digest, encode, fields, integer, parse, sha, text
from .study_outcomes import outcome


def validate_receipt(value, *, schema="hypersearch.study-receipt/v1", validate=validate_wrapper,
                     identity=execution_identity, judge=outcome):
    fields(value, "schema execution execution_sha256 task_id outcome outcome_sha256 attempt runtime diagnostics replay_matches_parent")
    if value["schema"] != schema:
        raise ValueError("unsupported receipt schema")
    execution = validate(value["execution"])
    task_id, specification = identity(execution)
    if value["task_id"] != task_id or value["execution_sha256"] != specification:
        raise ValueError("receipt task or full-wrapper identity mismatch")
    judge(value["outcome"], execution["bundle"])
    if value["outcome_sha256"] != digest(encode(value["outcome"])):
        raise ValueError("receipt outcome digest mismatch")
    fields(value["attempt"], "worker fence")
    text(value["attempt"]["worker"]); integer(value["attempt"]["fence"], 1, 2**63 - 1)
    fields(value["runtime"], "python implementation core_commit elapsed_ms")
    text(value["runtime"]["python"]); text(value["runtime"]["implementation"])
    if value["runtime"]["core_commit"] != execution["bundle"]["instrument"]["commit"]:
        raise ValueError("receipt runtime instrument mismatch")
    integer(value["runtime"]["elapsed_ms"], 0, 2**63 - 1)
    if type(value["diagnostics"]) is not str or len(value["diagnostics"]) > 4096:
        raise ValueError("invalid diagnostic record")
    comparison = value["replay_matches_parent"]
    if (execution["kind"] == "original" and comparison is not None
            or execution["kind"] == "replay" and type(comparison) is not bool):
        raise ValueError("invalid replay comparison")
    return value


def trusted_receipt(raw, expected_digest, *, validator=validate_receipt):
    # expected_digest must come from a separate committed manifest or Store row.
    sha(expected_digest)
    if digest(raw) != expected_digest:
        raise ValueError("receipt differs from external digest commitment")
    return validator(parse(raw, MAX_RECEIPT_BYTES))


def export_receipt(value, directory, *, validator=validate_receipt):
    validator(value)
    raw = encode(value)
    directory = Path(directory)
    directory.mkdir(exist_ok=True)
    destination = directory / (digest(raw) + ".json")
    # Atomic create without replacing an existing committed/damaged receipt.
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != raw:
            raise ValueError("receipt export collision or corruption")
        return destination
    descriptor, temporary = tempfile.mkstemp(prefix=".receipt-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != raw:
                raise ValueError("receipt export collision or corruption")
        dirfd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        os.unlink(temporary)
    return destination
