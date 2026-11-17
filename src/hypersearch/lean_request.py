"""Draft evaluator/candidate binding. Pure validation, never proof acceptance."""
import re

from .lean_snapshot import snapshot_digest, validate_snapshot
from .study_json import digest, encode, fields, sha

QUESTION_SCHEMA = "hypersearch.lean-question/draft1"
CANDIDATE_SCHEMA = "hypersearch.lean-candidate/draft1"
CHECKERS = ("lean-default", "lean-paranoid", "lean4lean", "nanoda", "con-leche", "con-ron")
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*\Z")


def identifier(value):
    if type(value) is not str or len(value) > 256 or not NAME.fullmatch(value):
        raise ValueError("unsupported Lean identifier")


def question_digest(value):
    fields(value, "schema challenge_module solution_module declaration challenge_snapshot_sha256 "
                  "dependency_snapshot_sha256 runtime_sha256 evaluator_sha256 allowed_axioms checkers")
    if value["schema"] != QUESTION_SCHEMA:
        raise ValueError("unsupported question schema")
    for field in ("challenge_module", "solution_module", "declaration"):
        identifier(value[field])
    for field in ("challenge_snapshot_sha256", "dependency_snapshot_sha256",
                  "runtime_sha256", "evaluator_sha256"):
        sha(value[field])
    # This draft supports only the constructive, empty-axiom policy.
    if type(value["allowed_axioms"]) is not list or value["allowed_axioms"]:
        raise ValueError("draft requires an empty axiom policy")
    fields(value["checkers"], " ".join(CHECKERS))
    for binary_digest in value["checkers"].values():
        sha(binary_digest)
    return digest(encode(value))


def bind_candidate(question, *, expected_question_sha256, challenge_snapshot, candidate):
    """Bind to a digest supplied by the evaluator, outside the candidate envelope.

    The caller must obtain the expected digest from a trusted frozen task. This
    helper cannot authenticate callers, check binaries, elaborate Lean, or issue
    a receipt. Dependency/runtime digests are required references, not checks.
    """
    sha(expected_question_sha256)
    actual_question = question_digest(question)
    if actual_question != expected_question_sha256:
        raise ValueError("question differs from evaluator's frozen identity")
    fields(candidate, "schema question_sha256 source_snapshot")
    if candidate["schema"] != CANDIDATE_SCHEMA:
        raise ValueError("unsupported candidate schema")
    sha(candidate["question_sha256"])
    if candidate["question_sha256"] != actual_question:
        raise ValueError("candidate is for a different question")
    challenge_digest = snapshot_digest(challenge_snapshot)
    if challenge_digest != question["challenge_snapshot_sha256"]:
        raise ValueError("challenge snapshot differs from frozen question")
    challenge_path = question["challenge_module"].replace(".", "/") + ".lean"
    solution_path = question["solution_module"].replace(".", "/") + ".lean"
    if challenge_path not in validate_snapshot(challenge_snapshot):
        raise ValueError("challenge module source missing")
    if solution_path not in validate_snapshot(candidate["source_snapshot"]):
        raise ValueError("solution module source missing")
    source_digest = snapshot_digest(candidate["source_snapshot"])
    identity = {"schema": CANDIDATE_SCHEMA, "question_sha256": actual_question,
                "source_snapshot_sha256": source_digest}
    return {**identity, "candidate_sha256": digest(encode(identity))}
