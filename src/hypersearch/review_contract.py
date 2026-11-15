"""Closed provenance contracts; authored findings are not established facts."""
from .study_json import artifact_bytes, digest, encode, fields, integer, sha, text

BUNDLE = "hypersearch.review-bundle/v1"
GRANT = "hypersearch.review-grant/v1"
REPORT = "hypersearch.review-report/v1"
RECEIPT = "hypersearch.review-receipt/v1"
SCHEMAS = {BUNDLE, GRANT, REPORT, RECEIPT}
ROLES = {"proof-author", "literature-reviewer", "hostile-reviewer", "methodology-reviewer"}


def labels(value):
    if type(value) is not list or len(value) > 64:
        raise ValueError("invalid declared lineage")
    for item in value:
        text(item)
    if len(set(value)) != len(value):
        raise ValueError("duplicate lineage label")


def bundle(value):
    fields(value, "schema review_id question role reviewer lineage exclusions parent consumer instrument artifacts protocol limits")
    if value["schema"] != BUNDLE:
        raise ValueError("unsupported review bundle")
    for key in ("review_id", "question", "reviewer"):
        text(value[key])
    if value["role"] not in ROLES:
        raise ValueError("unsupported review role")
    labels(value["lineage"]); labels(value["exclusions"])
    if value["reviewer"] not in value["lineage"]:
        raise ValueError("reviewer missing from declared orchestration lineage")
    if value["role"] != "proof-author" and set(value["lineage"]) & set(value["exclusions"]):
        raise ValueError("declared reviewer/contributor role conflict")
    if value["parent"] is not None:
        fields(value["parent"], "task_id receipt_sha256")
        text(value["parent"]["task_id"]); sha(value["parent"]["receipt_sha256"])
    fields(value["consumer"], "repository commit")
    fields(value["instrument"], "repository commit release_version api source_sha256")
    for name in ("consumer", "instrument"):
        text(value[name]["repository"]); sha(value[name]["commit"], 40)
    instrument = value["instrument"]
    if instrument["repository"].removesuffix(".git") != "https://github.com/SzeChunYiu/hypersearch":
        raise ValueError("unexpected core repository")
    text(instrument["release_version"]); text(instrument["api"])
    if type(instrument["source_sha256"]) is not dict or not instrument["source_sha256"]:
        raise ValueError("missing core source inventory")
    for identity in instrument["source_sha256"].values():
        sha(identity)
    artifacts = value["artifacts"]
    if type(artifacts) is not dict or not 1 <= len(artifacts) <= 16:
        raise ValueError("invalid review input collection")
    paths = []
    for name, item in artifacts.items():
        text(name); artifact_bytes(item); paths.append(item["path"])
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate artifact path")
    text(value["protocol"])
    if value["protocol"] not in artifacts:
        raise ValueError("protocol must identify a frozen input artifact")
    fields(value["limits"], "db_max_attempts lease_seconds")
    integer(value["limits"]["db_max_attempts"], 1, 2**63-1)
    integer(value["limits"]["lease_seconds"], 1, 86400)
    if len(encode(value)) > 1048576:
        raise ValueError("review bundle too large")
    return value


def identity(value):
    bundle(value)
    return "review-" + digest(encode({"namespace": BUNDLE, "review_id": value["review_id"]}))


def grant(value, frozen):
    fields(value, "schema task_id bundle_sha256 worker fence expires_at")
    if (value["schema"] != GRANT or value["task_id"] != identity(frozen)
            or value["bundle_sha256"] != digest(encode(frozen))
            or value["worker"] != frozen["reviewer"]):
        raise ValueError("grant differs from frozen review")
    integer(value["fence"], 1, 2**63-1)
    text(value["expires_at"])
    # Store timestamps are finite floats; their exact repr is a string in strict JSON.
    import math
    expiry = float(value["expires_at"])
    if not math.isfinite(expiry) or expiry < 0 or repr(expiry) != value["expires_at"]:
        raise ValueError("invalid grant expiry")
    return value


def report(value, frozen, token):
    fields(value, "schema task_id bundle_sha256 grant_sha256 reviewer role outcome findings_kind report evidence")
    if (value["schema"] != REPORT or value["task_id"] != identity(frozen)
            or value["bundle_sha256"] != digest(encode(frozen))
            or value["grant_sha256"] != digest(encode(token))
            or value["reviewer"] != frozen["reviewer"] or value["role"] != frozen["role"]):
        raise ValueError("report/task/grant binding mismatch")
    if value["findings_kind"] != "author_provided_not_independently_established":
        raise ValueError("report cannot establish its own findings")
    if value["outcome"] not in {"supports", "objects", "inconclusive", "failed", "incomplete"}:
        raise ValueError("unsupported declared review outcome")
    artifact_bytes(value["report"])
    if type(value["evidence"]) is not list or len(value["evidence"]) > 8:
        raise ValueError("invalid report evidence")
    paths = [value["report"]["path"]]
    for item in value["evidence"]:
        artifact_bytes(item); paths.append(item["path"])
    if len(set(paths)) != len(paths) or len(encode(value)) > 1048576:
        raise ValueError("duplicate or oversized report artifacts")
    return value


def receipt(value):
    fields(value, "schema bundle grant report report_sha256 verification claim_authority independence")
    if (value["schema"] != RECEIPT or value["verification"] != "NOT_FORMALLY_VERIFIED"
            or value["claim_authority"] != "none" or value["independence"] != "declared_not_authenticated"):
        raise ValueError("invalid review receipt scope")
    bundle(value["bundle"]); grant(value["grant"], value["bundle"])
    report(value["report"], value["bundle"], value["grant"])
    if value["report_sha256"] != digest(encode(value["report"])) or len(encode(value)) > 3145728:
        raise ValueError("review receipt report identity or size mismatch")
    return value
