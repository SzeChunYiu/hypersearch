"""A bounded trusted demo runner, not an arbitrary-code or model worker."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys

from . import __version__
from .math_adapter import search, verify_certificate
from .store import Store, canonical_json

VERIFIER = "hypersearch.zero-sum-subsets/v1"


def execute_spec(spec):
    """Execute only the bundled, versioned adapter on a closed specification."""
    if (type(spec) is not dict or set(spec) != {"schema", "domain", "moduli", "max_steps", "verifier"}
            or spec["schema"] != "hypersearch.task/v1"
            or spec["domain"] != "finite-abelian-zero-sum"
            or spec["verifier"] != VERIFIER):
        raise ValueError("unsupported frozen specification or verifier")
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
    status = sub.add_parser("status", help="inspect raw queue state (not certification)")
    status.add_argument("--db", required=True)
    status.add_argument("--budget", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            path = Path(args.certificate)
            if path.stat().st_size > 65536:
                raise ValueError("certificate exceeds 64 KiB")
            receipt = verify_certificate(json.loads(path.read_text()), expected_moduli=args.moduli)
            print(json.dumps(receipt, indent=2))
            return 0 if receipt["verified"] else 1
        store = Store(args.db, max_attempts=args.budget)
        if args.command == "status":
            print(json.dumps(store.snapshot(), indent=2))
            return 0
        spec = {"schema": "hypersearch.task/v1", "domain": "finite-abelian-zero-sum",
                "moduli": args.moduli, "max_steps": args.max_steps, "verifier": VERIFIER}
        task_id = "math-" + hashlib.sha256(canonical_json(spec).encode()).hexdigest()
        store.submit(task_id, spec)
        # Acquire may select earlier pending work; always execute its frozen spec.
        lease = store.acquire("local-bundled-worker", lease_seconds=300)
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
    except (ValueError, OSError, sqlite3.Error, RecursionError) as error:
        print(f"hypersearch: {error}", file=sys.stderr)
        return 2
