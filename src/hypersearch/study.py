"""Synchronous frozen supplied-certificate tasks using the existing Store."""
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

from .store import Store
from .study_contract import execution_identity, validate_wrapper, wrapper
from .study_json import MAX_BUNDLE_BYTES, MAX_RECEIPT_BYTES, digest, encode, parse
from .study_outcomes import outcome, verification
from .study_paths import output_paths, verify_sources
from .study_receipts import export_receipt, trusted_receipt, validate_receipt

CORE_ROOT = Path(__file__).resolve().parents[2]


def study_route():
    """The supplied-witness route. Built per call so tests can patch this module."""
    return SimpleNamespace(
        validate_wrapper=validate_wrapper, execution_identity=execution_identity, wrapper=wrapper,
        validate_receipt=validate_receipt, trusted_receipt=trusted_receipt, run=run_verifier, outcome=outcome,
        receipt_schema="hypersearch.study-receipt/v1", worker="local-bundled-study", required=None,
        exits={"VERIFIED_WITNESS": 0, "REFUTED_WITNESS": 1}, commands=("run-study", "replay-study"))


def run_verifier(bundle, core):
    """Bounded trusted child, isolated from ambient imports and credentials."""
    return run_child(bundle, core, "hypersearch.study_worker", verification)


def run_child(bundle, core, module, interpret):
    """Run one fixed bundled worker module; its output is interpreted by the parent."""
    environment = {"PATH": os.defpath, "PYTHONPATH": str(core / "src"),
                   "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory(prefix="hypersearch-study-") as work:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                result = subprocess.run(
                    [sys.executable, "-B", "-S", "-P", "-X", "pycache_prefix=" + work + "/bytecode",
                     "-m", module], input=encode(bundle), stdout=out, stderr=err,
                    cwd=work, env=environment, timeout=bundle["limits"]["timeout_seconds"], check=False)
            except subprocess.TimeoutExpired:
                return {"status": "INCOMPLETE", "verification": None}, "verifier timeout"
            out.seek(0); err.seek(0)
            if result.returncode != 0:
                detail = err.read(4096).decode("utf-8", errors="replace")
                return {"status": "EXECUTION_FAILED", "verification": None}, detail[:4096]
            return interpret(parse(out.read(65537), 65536), bundle), ""


def execute(execution, *, consumer_root, database, export, inputs=(), parent_receipt=None, route=None):
    route = route or study_route()
    route.validate_wrapper(execution)
    bundle = execution["bundle"]
    if execution["kind"] == "replay":
        if parent_receipt is None:
            raise ValueError("replay requires externally committed parent receipt")
        route.validate_receipt(parent_receipt)
        if (digest(encode(parent_receipt)) != execution["parent_receipt_sha256"]
                or parent_receipt["execution"]["bundle"] != bundle):
            raise ValueError("replay parent or frozen bundle mismatch")
    elif parent_receipt is not None:
        raise ValueError("original execution cannot carry a replay parent")
    core, consumer = verify_sources(bundle, CORE_ROOT, consumer_root, required=route.required)
    database, export = output_paths(database, export, (core, consumer), inputs)
    store = Store(database, max_attempts=bundle["limits"]["db_max_attempts"])
    task_id, specification = route.execution_identity(execution)
    # Stable replay ID binds once, atomically, before any grant. Changing its
    # parent or bundle conflicts with Store.submit's immutable specification.
    store.submit(task_id, execution)
    snapshot = store.snapshot()
    task = next(t for t in snapshot["tasks"] if t["id"] == task_id)
    if task["digest"] != specification or task["spec"].encode() != encode(execution):
        raise ValueError("stored task identity mismatch")
    existing = next((r for r in snapshot["results"] if r["task_id"] == task_id), None)
    if task["state"] == "completed" and existing is None:
        raise ValueError("completed task is missing its receipt")
    if existing is not None:
        receipt = route.trusted_receipt(existing["result"].encode(), existing["digest"])
        if (receipt["execution"] != execution or existing["result"].encode() != encode(receipt)
                or task["state"] != "completed" or existing["fence"] != task["fence"]
                or receipt["attempt"] != {"worker": task["worker"], "fence": task["fence"]}):
            raise ValueError("stored receipt identity or task linkage mismatch")
        path = export_receipt(receipt, export, validator=route.validate_receipt)
        return {"execution": "not_rerun", "receipt_sha256": digest(encode(receipt)), "receipt_path": str(path),
                "outcome_status": receipt["outcome"]["status"], "replay_matches_parent": receipt["replay_matches_parent"]}
    duration = bundle["limits"]["timeout_seconds"] + bundle["limits"]["commit_margin_seconds"]
    lease = store.acquire(route.worker, lease_seconds=duration, task_id=task_id)
    if lease is None:
        # Say which of the two refusals this is: a family of tasks sharing one database needs a
        # ceiling of at least one attempt per task, and an exhausted ceiling must not look like a busy task.
        after = store.snapshot()
        budget = after["budget"]
        state = next(t["state"] for t in after["tasks"] if t["id"] == task_id)
        exhausted = budget["spent"] >= budget["maximum"]
        return {"execution": "not_started", "task_id": task_id, "budget": budget, "task_state": state,
                "reason": "attempt budget exhausted" if exhausted else "task is leased to another attempt"}
    started = time.monotonic()
    diagnostics = ""
    try:
        frozen = route.validate_wrapper(parse(lease.spec_json.encode()))
        if frozen != execution:
            raise ValueError("leased execution differs from admitted wrapper")
        result, diagnostics = route.run(frozen["bundle"], core)
        route.outcome(result, frozen["bundle"])
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError, RecursionError) as error:
        result = {"status": "EXECUTION_FAILED", "verification": None}
        diagnostics = str(error)[:4096]
    receipt = {"schema": route.receipt_schema, "execution": execution,
               "execution_sha256": specification, "task_id": task_id, "outcome": result, "outcome_sha256": digest(encode(result)),
               "attempt": {"worker": lease.worker, "fence": lease.fence},
               "runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                           "core_commit": bundle["instrument"]["commit"],
                           "elapsed_ms": int((time.monotonic() - started) * 1000)},
               "diagnostics": diagnostics,
               "replay_matches_parent": (None if parent_receipt is None  # by encoding: 1 == True in Python
                                         else encode(result) == encode(parent_receipt["outcome"]))}
    route.validate_receipt(receipt)
    # Stale/expired completion raises; nothing is exported before the commit.
    result_digest = store.complete(lease, receipt)
    if result_digest != digest(encode(receipt)):
        raise ValueError("stored result encoding identity mismatch")
    path = export_receipt(receipt, export, validator=route.validate_receipt)
    return {"execution": "completed", "receipt_sha256": result_digest, "receipt_path": str(path),
            "outcome_status": result["status"], "replay_matches_parent": receipt["replay_matches_parent"]}


def main(args, route=None):
    route = route or study_route()
    if args.command == route.commands[0]:
        with open(args.bundle, "rb") as source:
            bundle = parse(source.read(MAX_BUNDLE_BYTES + 1))
        execution = route.wrapper(bundle)
        parent = None
        inputs = (args.bundle,)
    else:
        with open(args.receipt, "rb") as source:
            raw = source.read(MAX_RECEIPT_BYTES + 1)
        parent = route.trusted_receipt(raw, args.expected_receipt_sha256)
        # Exports use canonical bytes; reject alternate serialization for replay.
        if raw != encode(parent):
            raise ValueError("receipt is not in the committed encoding")
        execution = route.wrapper(parent["execution"]["bundle"],
                                  parent=args.expected_receipt_sha256, replay_id=args.replay_id)
        inputs = (args.receipt,)
    result = execute(execution, consumer_root=args.consumer_root, database=args.db,
                     export=args.export, inputs=inputs, parent_receipt=parent, route=route)
    print(encode(result).decode("ascii"))
    if result.get("replay_matches_parent") is False:
        return 2
    return route.exits.get(result.get("outcome_status"), 2)
