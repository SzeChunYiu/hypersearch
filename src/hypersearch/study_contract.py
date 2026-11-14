"""Closed frozen-study admission; never execute candidates during validation."""
from . import __version__
from .math_adapter import validate_certificate as ordinary_admission
from .multiwise import validate_certificate as multiwise_admission
from .study_json import MAX_BUNDLE_BYTES, artifact_bytes, digest, encode, fields, integer, parse, relative, sha, text

REPOSITORY = "https://github.com/SzeChunYiu/hypersearch.git"
VERIFIERS = {"ordinary-witness": "hypersearch.zero-sum-subsets/v1",
             "multiwise-witness": "hypersearch.multiwise-subsets/v1"}
ARTIFACTS = {"study_manifest", "preregistration", "claim_record", "certificate"}


def validate_bundle(value):
    fields(value, "schema study_id consumer instrument question artifacts limits")
    if value["schema"] != "hypersearch.study-bundle/v1":
        raise ValueError("unsupported study bundle")
    text(value["study_id"])
    consumer, instrument = value["consumer"], value["instrument"]
    fields(consumer, "repository commit claim_id claim_record_sha256 preregistration_sha256 entrypoint entrypoint_sha256")
    text(consumer["repository"]); text(consumer["claim_id"])
    sha(consumer["commit"], 40); relative(consumer["entrypoint"])
    for key in ("claim_record_sha256", "preregistration_sha256", "entrypoint_sha256"):
        sha(consumer[key])
    fields(instrument, "repository commit release_version api verifier source_sha256")
    if (instrument["repository"] != REPOSITORY or instrument["release_version"] != __version__
            or instrument["api"] != "hypersearch.api/v1"):
        raise ValueError("unsupported instrument identity")
    sha(instrument["commit"], 40)
    sources = instrument["source_sha256"]
    if type(sources) is not dict or not sources:
        raise ValueError("missing instrument source identities")
    for path, value_sha in sources.items():
        relative(path); sha(value_sha)
    fields(value["artifacts"], "study_manifest preregistration claim_record certificate")
    artifacts = value["artifacts"]
    raw = {name: artifact_bytes(item, 65536 if name in {"certificate", "study_manifest"} else 262144)
           for name, item in artifacts.items()}
    if len({a["path"] for a in artifacts.values()} | {consumer["entrypoint"]}) != 5:
        raise ValueError("artifact paths must be distinct")
    if (consumer["claim_record_sha256"] != artifacts["claim_record"]["sha256"]
            or consumer["preregistration_sha256"] != artifacts["preregistration"]["sha256"]):
        raise ValueError("consumer reference mismatch")
    claim = parse(raw["claim_record"])
    if type(claim) is not dict or claim.get("id") != consumer["claim_id"]:
        raise ValueError("claim identity mismatch")
    limits = value["limits"]
    fields(limits, "db_max_attempts timeout_seconds commit_margin_seconds max_certificate_bytes")
    integer(limits["db_max_attempts"], 1, 2**63 - 1)
    integer(limits["timeout_seconds"], 1, 60)
    integer(limits["commit_margin_seconds"], 1, 60)
    if type(limits["max_certificate_bytes"]) is not int or limits["max_certificate_bytes"] != 65536:
        raise ValueError("unsupported certificate byte policy")
    question = value["question"]
    fields(question, "adapter moduli k length claim_type intended_bound assumptions_sha256")
    if type(question["moduli"]) is not list:
        raise ValueError("group presentation must be an explicit list")
    adapter = question["adapter"]
    if type(adapter) is not str or adapter not in VERIFIERS or instrument["verifier"] != VERIFIERS[adapter]:
        raise ValueError("unsupported adapter or verifier")
    integer(question["k"], 1, 16); integer(question["length"], 0, 16)
    integer(question["intended_bound"], 1, 17)
    if (question["claim_type"] != "lower-bound-witness"
            or question["intended_bound"] != question["length"] + 1
            or question["assumptions_sha256"] != artifacts["preregistration"]["sha256"]):
        raise ValueError("unsupported question scope")
    manifest = parse(raw["study_manifest"])
    fields(manifest, "schema study_id question limits artifact_sha256")
    if (manifest["schema"] != "hypersearch.study-manifest/v1" or manifest["study_id"] != value["study_id"]
            or encode(manifest["question"]) != encode(question) or encode(manifest["limits"]) != encode(limits)
            or manifest["artifact_sha256"] != {k: v["sha256"] for k, v in artifacts.items() if k != "study_manifest"}):
        raise ValueError("frozen manifest binding mismatch")
    certificate = parse(raw["certificate"], 65536)
    if adapter == "ordinary-witness":
        if question["k"] != 1:
            raise ValueError("ordinary witness requires k=1")
        ordinary_admission(certificate, expected_moduli=question["moduli"])
    else:
        multiwise_admission(certificate, expected_moduli=question["moduli"], expected_k=question["k"])
    if len(certificate["sequence"]) != question["length"]:
        raise ValueError("frozen sequence length mismatch")
    return value


def wrapper(bundle, *, parent=None, replay_id=None):
    value = {"schema": "hypersearch.study-execution/v1", "kind": "original" if parent is None else "replay",
             "bundle": bundle, "parent_receipt_sha256": parent, "replay_id": replay_id}
    return validate_wrapper(value)


def validate_wrapper(value):
    fields(value, "schema kind bundle parent_receipt_sha256 replay_id")
    if (value["schema"] != "hypersearch.study-execution/v1" or type(value["kind"]) is not str
            or value["kind"] not in {"original", "replay"}):
        raise ValueError("unsupported execution wrapper")
    if value["kind"] == "original":
        if value["parent_receipt_sha256"] is not None or value["replay_id"] is not None:
            raise ValueError("original execution cannot select a replay identity")
    else:
        sha(value["parent_receipt_sha256"]); text(value["replay_id"])
    validate_bundle(value["bundle"])
    if len(encode(value)) > MAX_BUNDLE_BYTES:
        raise ValueError("execution wrapper exceeds admitted byte bound")
    return value
