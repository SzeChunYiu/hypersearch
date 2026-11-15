"""Register/grant/ingest external reports through the sole existing Store."""
from pathlib import Path
import sqlite3
from .store import Store, Lease, StaleLease
from . import review_contract as contract
from .review_sources import sources
from .study_json import digest, encode, parse
from .study_paths import output_paths
from .study_receipts import export_receipt

CORE_ROOT = Path(__file__).resolve().parents[2]


def read_state(database, task_id):
    # Admission reads never create or initialize a DB, even for a forged grant.
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        result = db.execute("SELECT * FROM results WHERE task_id=?", (task_id,)).fetchone()
        budget = db.execute("SELECT * FROM budget WHERE id=1").fetchone()
        return dict(row) if row else None, dict(result) if result else None, dict(budget)


def task_state(database, value):
    task, result, budget = read_state(database, contract.identity(value))
    if (task is None or task["spec"].encode() != encode(value)
            or task["digest"] != digest(encode(value))
            or budget["maximum"] != value["limits"]["db_max_attempts"]):
        raise ValueError("stored review specification or allowance mismatch")
    return task, result


def admit(value, consumer_root, database, export, inputs, parent_raw):
    contract.bundle(value)
    roots = sources(value, CORE_ROOT, consumer_root, parent_raw)
    return output_paths(database, export, roots, inputs)


def register(value, *, consumer_root, database, export, inputs=(), parent_raw=None):
    database, _ = admit(value, consumer_root, database, export, inputs, parent_raw)
    store = Store(database, value["limits"]["db_max_attempts"])
    store.submit(contract.identity(value), value)
    return {"task_id": contract.identity(value), "bundle_sha256": digest(encode(value)), "status": "registered"}


def grant(value, *, consumer_root, database, export, inputs=(), parent_raw=None):
    database, _ = admit(value, consumer_root, database, export, inputs, parent_raw)
    task_state(database, value)
    store = Store(database, value["limits"]["db_max_attempts"])
    lease = store.acquire(value["reviewer"], value["limits"]["lease_seconds"], task_id=contract.identity(value))
    if lease is None:
        raise ValueError("review task unavailable")
    token = {"schema": contract.GRANT, "task_id": lease.task_id, "bundle_sha256": lease.spec_digest,
             "worker": lease.worker, "fence": lease.fence, "expires_at": repr(lease.expires_at)}
    contract.grant(token, value)
    return token


def submit(value, token, report, *, consumer_root, database, export, inputs=(), parent_raw=None):
    contract.bundle(value); contract.grant(token, value); contract.report(report, value, token)
    database, export = admit(value, consumer_root, database, export, inputs, parent_raw)
    task, _ = task_state(database, value)
    if (task["state"] != "running" or task["worker"] != token["worker"]
            or task["fence"] != token["fence"] or repr(task["expires"]) != token["expires_at"]):
        raise StaleLease("review grant is not current in Store")
    lease = Lease(task["id"], task["worker"], task["fence"], task["expires"], task["spec"], task["digest"])
    result = {"schema": contract.RECEIPT, "bundle": value, "grant": token, "report": report,
              "report_sha256": digest(encode(report)), "verification": "NOT_FORMALLY_VERIFIED",
              "claim_authority": "none", "independence": "declared_not_authenticated"}
    contract.receipt(result)
    store = Store(database, value["limits"]["db_max_attempts"])
    committed = store.complete(lease, result)  # atomic expiry/fence/worker/spec authority
    if committed != digest(encode(result)):
        raise ValueError("receipt encoding mismatch")
    path = export_receipt(result, export, validator=contract.receipt)
    return {"receipt_sha256": committed, "receipt_path": str(path), "verification": "NOT_FORMALLY_VERIFIED"}


def recover(value, *, consumer_root, database, export, inputs=(), parent_raw=None):
    database, export = admit(value, consumer_root, database, export, inputs, parent_raw)
    task, row = task_state(database, value)
    if row is None or task["state"] != "completed" or row["fence"] != task["fence"]:
        raise ValueError("no linked completed review receipt")
    raw = row["result"].encode()
    if digest(raw) != row["digest"]:
        raise ValueError("stored receipt digest mismatch")
    result = contract.receipt(parse(raw, 3145728))
    token = result["grant"]
    if (encode(result) != raw or encode(result["bundle"]) != encode(value)
            or token["fence"] != task["fence"] or token["worker"] != task["worker"]
            or token["expires_at"] != repr(task["expires"])):
        raise ValueError("stored receipt linkage mismatch")
    path = export_receipt(result, export, validator=contract.receipt)
    return {"receipt_sha256": row["digest"], "receipt_path": str(path), "verification": "NOT_FORMALLY_VERIFIED"}
