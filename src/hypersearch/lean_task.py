"""Draft Lean registration in the existing Store; no grant or execution route."""
from .lean_request import bind_candidate
from .study_json import MAX_BUNDLE_BYTES, digest, encode, fields, integer, parse

SCHEMA = "hypersearch.lean-task/draft1"


def prepare_task(question, *, expected_question_sha256, challenge_snapshot, candidate, limits):
    """Return detached frozen input bytes/identity after all pure validation.

    The expected question identity must come from the evaluator's task authority,
    never from the candidate. Limits are evaluator-owned as well. A prepared
    task is not an executable grant, validated runtime, or mathematical receipt.
    """
    binding = bind_candidate(question, expected_question_sha256=expected_question_sha256,
                             challenge_snapshot=challenge_snapshot, candidate=candidate)
    fields(limits, "timeout_seconds memory_megabytes")
    integer(limits["timeout_seconds"], 1, 3600)
    integer(limits["memory_megabytes"], 64, 65536)
    # Own a deep JSON copy. A caller retaining and mutating dictionaries must not
    # alter the bytes that will be submitted after validation.
    value = {"schema": SCHEMA, "question": question, "binding": binding,
             "challenge_snapshot": challenge_snapshot, "candidate": candidate,
             "limits": limits, "scope": "uncommissioned_lean_candidate"}
    frozen = parse(encode(value), MAX_BUNDLE_BYTES)
    for snapshot in (frozen["challenge_snapshot"], frozen["candidate"]["source_snapshot"]):
        snapshot["files"].sort(key=lambda item: item["path"])
    raw = encode(frozen)
    identity = digest(raw)
    return "lean-draft-" + identity, raw


def register_candidate(store, question, *, expected_question_sha256,
                       challenge_snapshot, candidate, limits):
    """Register only this immutable candidate, without acquiring pending work.

    The caller owns an already opened cooperative Store and its global budget.
    This function does not authenticate the caller or provide a CLI/source-pin
    admission boundary. No imported candidate code is executed.
    """
    task_id, raw = prepare_task(question, expected_question_sha256=expected_question_sha256,
                                challenge_snapshot=challenge_snapshot,
                                candidate=candidate, limits=limits)
    store.submit(task_id, parse(raw))
    return {"task_id": task_id, "specification_sha256": digest(raw),
            "scope": "registered_candidate_only"}
