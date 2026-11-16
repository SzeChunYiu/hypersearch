"""A bounded trusted demo runner, not an arbitrary-code or model worker."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import signal
import sqlite3
import subprocess
import sys

from . import __version__
from .math_adapter import search, validate_search_inputs, verify_certificate
from .multiwise import verify_certificate as verify_multiwise
from .store import Store, canonical_json

VERIFIER = "hypersearch.zero-sum-subsets/v1"


def validate_spec(spec):
    """Admit a bundled task before opening a store or charging an attempt."""
    if (type(spec) is not dict or set(spec) != {"schema", "domain", "moduli", "max_steps", "verifier"}
            or spec["schema"] != "hypersearch.task/v1"
            or spec["domain"] != "finite-abelian-zero-sum"
            or spec["verifier"] != VERIFIER):
        raise ValueError("unsupported frozen specification or verifier")
    validate_search_inputs(spec["moduli"], spec["max_steps"])


def execute_spec(spec):
    """Revalidate leased work, then execute only the bundled adapter."""
    validate_spec(spec)
    certificate = search(spec["moduli"], max_steps=spec["max_steps"])
    receipt = verify_certificate(certificate, expected_moduli=spec["moduli"])
    if not receipt["verified"]:
        raise ValueError("bundled candidate failed independent recomputation")
    sources = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
               for name in ("cli.py", "math_adapter.py", "store.py")}
    return {"execution": "completed", "spec_sha256": hashlib.sha256(canonical_json(spec).encode()).hexdigest(),
            "certificate": certificate, "verification": receipt,
            "provenance": {"package_version": __version__, "python": platform.python_version(),
                           "source_sha256": sources, "verifier": VERIFIER},
            "scientific_status": "known-answer demonstration; novelty not assessed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="enqueue and execute one bounded mathematical task")
    demo.add_argument("--db", required=True)
    demo.add_argument("--moduli", nargs="+", type=int, default=[2, 2, 2])
    demo.add_argument("--max-steps", type=int, default=10000)
    demo.add_argument("--budget", type=int, default=100, help="fixed total attempts for this database")
    verify = sub.add_parser("verify", help="recheck a JSON certificate against an explicit group")
    verify.add_argument("certificate")
    verify.add_argument("--moduli", nargs="+", type=int, required=True)
    multi = sub.add_parser("verify-multiwise", help="check a bounded D_k lower-bound witness")
    multi.add_argument("certificate")
    multi.add_argument("--moduli", nargs="+", type=int, required=True)
    multi.add_argument("--k", type=int, required=True)
    status = sub.add_parser("status", help="inspect raw queue state (not certification)")
    status.add_argument("--db", required=True)
    status.add_argument("--budget", type=int, default=100)
    for name in ("run-study", "replay-study", "run-census", "replay-census", "run-program", "replay-program"):
        study = sub.add_parser(name, help="execute a frozen supplied-certificate, exhaustive-census or pinned-program task")
        study.add_argument("--consumer-root", required=True)
        study.add_argument("--db", required=True)
        study.add_argument("--export", required=True)
        if name.startswith("run-"):
            study.add_argument("--bundle", required=True)
        else:
            study.add_argument("--receipt", required=True)
            study.add_argument("--expected-receipt-sha256", required=True)
            study.add_argument("--replay-id", required=True)
    abandon = sub.add_parser("abandon-attempt", help="free a task whose launcher died holding it; deletes nothing")
    abandon.add_argument("--db", required=True, help="an existing task database")
    abandon.add_argument("--task", required=True, help="the task id, as a refused start prints it")
    abandon.add_argument("--fence", required=True, type=int, help="the fence of the lease to abandon")
    abandon.add_argument("--reason", required=True, help="why, recorded with the abandoned event")
    check = sub.add_parser("check-export", help="re-verify directories of exported receipts; runs and writes nothing")
    check.add_argument("--route", required=True, choices=("study", "census", "program"))
    check.add_argument("--export", required=True, action="append", help="a receipt directory; repeat for several")
    check.add_argument("--expected", help="a consumer's hypersearch.expected-outcomes/v1 file")
    from .review_cli import arguments as review_arguments
    review_arguments(sub)
    args = parser.parse_args(argv)
    try:
        if args.command.endswith(("-review", "-study", "-census", "-program", "-export")):
            if signal.getsignal(signal.SIGCHLD) == signal.SIG_IGN:  # inherited across exec, it loses every exit status
                signal.signal(signal.SIGCHLD, signal.SIG_DFL)
            from .study_paths import launch_boundary
            launch_boundary(Path(__file__).resolve().parents[2])
        if args.command.endswith("-review"):
            from .review_cli import main as review_main
            return review_main(args)
        if args.command in ("run-study", "replay-study"):
            from .study import main as study_main
            return study_main(args)
        if args.command in ("run-census", "replay-census"):
            from .census import main as census_main
            return census_main(args)
        if args.command in ("run-program", "replay-program"):
            from .program import main as program_main
            return program_main(args)
        if args.command == "abandon-attempt":
            from .holders import main as abandon_main
            return abandon_main(args)
        if args.command == "check-export":
            from .export_check import main as check_main
            return check_main(args)
        if args.command in ("verify", "verify-multiwise"):
            path = Path(args.certificate)
            if path.stat().st_size > 65536:
                raise ValueError("certificate exceeds 64 KiB")
            certificate = json.loads(path.read_text())
            if args.command == "verify-multiwise":
                receipt = verify_multiwise(certificate, expected_moduli=args.moduli, expected_k=args.k)
                receipt["verifier"] = "hypersearch.multiwise-subsets/v1"
            else:
                receipt = verify_certificate(certificate, expected_moduli=args.moduli)
            print(json.dumps(receipt, indent=2))
            return 0 if receipt["verified"] else 1
        if args.command == "demo":
            spec = {"schema": "hypersearch.task/v1", "domain": "finite-abelian-zero-sum",
                    "moduli": args.moduli, "max_steps": args.max_steps, "verifier": VERIFIER}
            validate_spec(spec)
        store = Store(args.db, max_attempts=args.budget)
        if args.command == "status":
            print(json.dumps(store.snapshot(), indent=2))
            return 0
        task_id = "math-" + hashlib.sha256(canonical_json(spec).encode()).hexdigest()
        store.submit(task_id, spec)
        # A bounded CLI request never grants work belonging to another contract.
        lease = store.acquire("local-bundled-worker", lease_seconds=300, task_id=task_id)
        if lease is None:
            print(json.dumps({"execution": "not_started", "reason": "no eligible task or attempt budget exhausted", "task_id": task_id}))
            return 0
        frozen = json.loads(lease.spec_json)
        try:
            result = execute_spec(frozen)
        except ValueError as error:
            store.complete(lease, {"execution": "failed", "reason": str(error), "scientific_status": "unverified"})
            raise
        digest = store.complete(lease, result)
        print(json.dumps({"task_id": lease.task_id, "result_sha256": digest, **result}, indent=2))
        return 0
    except (ValueError, TypeError, OSError, sqlite3.Error, subprocess.SubprocessError, RecursionError) as error:
        print(f"hypersearch: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # exit 1 means a completed refutation; a crash must never read as one
        import traceback
        traceback.print_exc()
        print(f"hypersearch: internal failure: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
