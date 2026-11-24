"""Re-verify directories of exported receipts. Read-only: no database, verifier or program is touched.

Every receipt is admitted by its route's own validator. The report says what the files are and
whether they agree with what a consumer wrote down beforehand; it accepts no claim.
"""
import os
from pathlib import Path

from . import __version__
from .census import census_route
from .program import program_route
from .study import study_route
from .study_contract import READ_RELEASES
from .study_json import MAX_BUNDLE_BYTES, MAX_RECEIPT_BYTES, digest, encode, fields, parse, sha, text

ROUTES = {"study": study_route, "census": census_route, "program": program_route}
EXPECTED_SCHEMA = "hypersearch.expected-outcomes/v1"
REFUSED = (ValueError, TypeError, KeyError, RecursionError)
# Read here only: their receipt validators equal this release's but for the version. Review at every release.
EARLIER = frozenset({"0.7.0", "0.7.1", "0.8.0", "0.9.0"})


def problem(kind, subject):
    """A fixed string and the digest, study or path it is about; never file contents."""
    return {"problem": kind, "subject": subject}


def validate_expected(value, name, route):
    """Closed admission of a consumer's expected outcomes for one route."""
    fields(value, "schema require_replay studies")
    studies = value["studies"]
    if (value["schema"] != EXPECTED_SCHEMA or type(value["require_replay"]) is not bool
            or type(studies) is not dict or not studies):
        raise ValueError("unsupported expected outcomes")
    for study_id, wanted in studies.items():
        text(study_id)
        fields(wanted, "status summary_sha256 unregistered_summary_fields")
        if type(wanted["status"]) is not str or wanted["status"] not in {*route.exits, "EXECUTION_FAILED", "INCOMPLETE"}:
            raise ValueError("expected status is not an outcome status of this route")
        names = wanted["unregistered_summary_fields"]
        if type(names) is not list or len(names) > 64:
            raise ValueError("unregistered summary fields must be a short list")
        for item in names:
            text(item)
        if len(set(names)) != len(names):
            raise ValueError("unregistered summary fields repeat a name")
        if wanted["summary_sha256"] is None:
            if names:
                raise ValueError("unregistered summary fields need a summary digest")
        else:
            sha(wanted["summary_sha256"])
            if name != "program":
                raise ValueError("a summary digest applies to the program route only")
    return value


def admit(route, entry):
    """One directory entry as (problem, digest, receipt): a problem, or a receipt under its digest."""
    if entry.is_symlink():
        return "symlink entry", None, None
    if not entry.name.endswith(".json") or not entry.is_file(follow_symlinks=False):
        return "not a regular .json file", None, None
    try:
        with open(entry.path, "rb") as source:
            raw = source.read(MAX_RECEIPT_BYTES + 1)
    except OSError:
        return "file cannot be read", None, None
    if len(raw) > MAX_RECEIPT_BYTES:
        return "file exceeds the receipt byte bound", None, None
    name = digest(raw)
    if entry.name != name + ".json":
        return "file name is not the digest of its bytes", None, None
    token = READ_RELEASES.set(EARLIER)
    try:
        receipt = route.trusted_receipt(raw, name)
    except REFUSED:
        return refusal(route, raw), None, None
    finally:
        READ_RELEASES.reset(token)
    if raw != encode(receipt):
        return "receipt is not in the committed encoding", None, None
    return None, name, receipt


def refusal(route, raw):
    """Why the validator refused, as far as two fixed cases can say."""
    try:
        value = parse(raw, MAX_RECEIPT_BYTES)
        schema, version = value["schema"], value["execution"]["bundle"]["instrument"]["release_version"]
    except REFUSED:
        return "receipt refused by the route's validator"
    if type(schema) is str and schema != route.receipt_schema and schema in {make().receipt_schema for make in ROUTES.values()}:
        return "receipt belongs to another route"
    if type(version) is str and version not in EARLIER | {__version__}:  # only these versions are read
        return "receipt names another instrument version"
    return "receipt refused by the route's validator"


def compare(replay, parent):
    """Recompute a replay's comparison with its parent. The stored flag is checked, never trusted."""
    if parent is None:
        return None, ["replay parent is absent"]
    faults = []
    if parent["execution"]["kind"] != "original":
        faults.append("replay parent is not an original")
    if encode(parent["execution"]["bundle"]) != encode(replay["execution"]["bundle"]):
        faults.append("replay bundle differs from its parent")
    if faults:
        return None, faults
    same = encode(replay["outcome"]) == encode(parent["outcome"])  # by encoding: 1 == True in Python
    if replay["replay_matches_parent"] is not same:
        faults.append("replay flag disagrees with the recomputed comparison")
    if not same:
        faults.append("replay does not match its parent")
    return same, faults


def expect(expected, studies, receipts, problems):
    """Hold the studies found against the consumer's expected outcomes."""
    problems += [problem("expected study is absent", name) for name in sorted(set(expected["studies"]) - set(studies))]
    for study_id, study in studies.items():
        wanted = expected["studies"].get(study_id)
        if wanted is None:
            study["problems"].append(problem("study is not listed in the expected outcomes", study_id))
            continue
        for row in study["originals"]:
            if row["outcome_status"] != wanted["status"]:
                study["problems"].append(problem("outcome status differs from the expected status", row["receipt_sha256"]))
            record = receipts[row["receipt_sha256"]]["outcome"]["verification"]
            if wanted["summary_sha256"] is not None and (record is None or wanted["summary_sha256"] != digest(encode(
                    {k: v for k, v in record["summary"].items() if k not in wanted["unregistered_summary_fields"]}))):
                study["problems"].append(problem("summary digest differs from the expected digest", row["receipt_sha256"]))
        if expected["require_replay"] and not study["replayed"]:
            study["problems"].append(problem("study has no matching replay", study_id))


def check(name, directories, expected=None):
    """Report on every entry directly in the directories; anything unexpected is a problem, never skipped."""
    if name not in ROUTES:
        raise ValueError("unknown route")
    route = ROUTES[name]()
    if expected is not None:
        validate_expected(expected, name, route)
    paths = [Path(directory) for directory in directories]
    if any(path.is_symlink() or not path.is_dir() for path in paths):
        raise ValueError("export path is not a directory")
    if not paths or len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("export directories must be given once each")
    receipts, problems, ignored = {}, [], 0
    for path in paths:
        found = 0
        for entry in sorted(os.scandir(path), key=lambda item: item.name):
            if entry.name.startswith("."):  # for example a staging file left by an interrupted export
                ignored += 1
                continue
            fault, key, receipt = admit(route, entry)
            if fault:
                problems.append(problem(fault, str(path / entry.name)))
            else:
                receipts[key] = receipt  # the same receipt in two directories is one receipt
                found += 1
        if not found:  # deleting the evidence must never read as a pass
            problems.append(problem("export directory holds no receipt", str(path)))
    studies = {}
    for key in sorted(receipts):
        receipt = receipts[key]
        execution = receipt["execution"]
        study = studies.setdefault(execution["bundle"]["study_id"], {"originals": [], "replays": [], "problems": []})
        row = {"receipt_sha256": key, "outcome_status": receipt["outcome"]["status"],
               "python": receipt["runtime"]["python"], "elapsed_ms": receipt["runtime"]["elapsed_ms"]}
        if execution["kind"] == "original":
            study["originals"].append(row)
            continue
        row["parent_receipt_sha256"] = execution["parent_receipt_sha256"]
        row["matches_parent"], faults = compare(receipt, receipts.get(row["parent_receipt_sha256"]))
        row["sound"] = not faults
        study["replays"].append(row)
        study["problems"] += [problem(fault, key) for fault in faults]
    for study_id, study in studies.items():
        if len(study["originals"]) != 1:
            study["problems"].append(problem("study has more than one original" if study["originals"]
                                             else "study has no original", study_id))
        study["replayed"] = any([row.pop("sound") for row in study["replays"]])  # a list: every row loses the key
    if expected is not None:
        expect(expected, studies, receipts, problems)
    return {"check": "export", "route": name, "receipts": len(receipts), "ignored_dot_files": ignored,
            "studies": studies, "problems": problems,
            "ok": not problems and not any(study["problems"] for study in studies.values())}


def main(args):
    expected, commitment = None, None
    if args.expected is not None:
        with open(args.expected, "rb") as source:
            raw = source.read(MAX_BUNDLE_BYTES + 1)
        expected, commitment = parse(raw), digest(raw)
        if expected is None:  # null is a malformed file, never "no expected outcomes"
            raise ValueError("unsupported expected outcomes")
    report = dict(check(args.route, args.export, expected), expected_sha256=commitment)
    print(encode(report).decode("ascii"))
    return 0 if report["ok"] else 1
