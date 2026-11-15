"""Exact local source pins for review provenance, not remote authentication."""
from pathlib import Path
from . import __version__
from .review_contract import SCHEMAS, receipt
from .study_json import artifact_bytes, digest, encode, parse
from .study_paths import checkout, plain_file


def sources(value, core_root, consumer_root, parent_raw=None):
    instrument, consumer = value["instrument"], value["consumer"]
    core, tracked = checkout(core_root, instrument["commit"], instrument["repository"])
    consumer_root, inputs = checkout(consumer_root, consumer["commit"], consumer["repository"])
    if core == consumer_root or core in consumer_root.parents or consumer_root in core.parents:
        raise ValueError("source roots overlap")
    expected = {p for p in tracked if p.startswith("src/hypersearch/") and p.endswith(".py")}
    expected.add("governance/release.json")
    if set(instrument["source_sha256"]) != expected:
        raise ValueError("core source inventory mismatch")
    for name in expected:
        if digest(plain_file(core, name).read_bytes()) != instrument["source_sha256"][name]:
            raise ValueError("core source hash mismatch")
    release = parse(plain_file(core, "governance/release.json").read_bytes())
    if (release.get("version") != instrument["release_version"] or release.get("version") != __version__
            or release.get("api") != instrument["api"] or not SCHEMAS <= set(release.get("schemas", []))
            or release.get("status") not in {"development", "release-candidate", "released"}):
        raise ValueError("review instrument version or schemas mismatch")
    for path in (core / "src").rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinked executable source")
        if (path.is_file() and "__pycache__" not in path.parts
                and path.suffix in {".py", ".pyc", ".so", ".pyd"}
                and path.relative_to(core).as_posix() not in tracked):
            raise ValueError("untracked executable source")
    for item in value["artifacts"].values():
        if item["path"] not in inputs or plain_file(consumer_root, item["path"]).read_bytes() != artifact_bytes(item):
            raise ValueError("review input differs from consumer source")
    if value["parent"] is None:
        if parent_raw is not None:
            raise ValueError("unexpected parent receipt")
    else:
        if parent_raw is None or digest(parent_raw) != value["parent"]["receipt_sha256"]:
            raise ValueError("parent receipt differs from frozen digest")
        parent = receipt(parse(parent_raw, 3145728))
        if (encode(parent) != parent_raw or parent["grant"]["task_id"] != value["parent"]["task_id"]):
            raise ValueError("parent receipt identity mismatch")
    return core, consumer_root
