"""Frozen consumer-program tasks on the same Store, lease, receipt and export path as studies."""
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from . import program_contract as contract
from . import study
from .study_json import artifact_bytes, encode, parse


def run_program(bundle, core):
    """Run the bundled program bytes, never the consumer's working file, in an isolated interpreter.

    Isolation is from ambient imports, environment and bytecode. It is not a security sandbox:
    the program runs with the operator's file and network access.
    """
    limits = bundle["limits"]
    memory = limits["memory_megabytes"] * 1048576

    def confine():
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    with tempfile.TemporaryDirectory(prefix="hypersearch-program-") as work:
        path = Path(work, "program.py")
        path.write_bytes(artifact_bytes(bundle["artifacts"]["program"]))
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            child = subprocess.Popen([sys.executable, "-B", "-I", "-S", str(path)], stdin=subprocess.PIPE, stdout=out,
                                     stderr=err, cwd=work, env={"PATH": os.defpath}, start_new_session=True,
                                     preexec_fn=confine)
            try:
                child.communicate(encode(bundle["question"]["arguments"]), timeout=limits["timeout_seconds"])
            except subprocess.TimeoutExpired:
                return {"status": "INCOMPLETE", "verification": None}, "program timeout"
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)  # the program and anything it started
                except ProcessLookupError:
                    pass
                child.wait()
            out.seek(0); err.seek(0)
            if child.returncode != 0:
                detail = err.read(4096).decode("utf-8", errors="replace")
                return {"status": "EXECUTION_FAILED", "verification": None}, detail[:4096]
            produced = parse(out.read(contract.MAX_OUTPUT_BYTES + 1), contract.MAX_OUTPUT_BYTES)
            return contract.verification(contract.record(produced, bundle), bundle), ""


def program_route():
    return SimpleNamespace(
        validate_wrapper=contract.validate_wrapper, execution_identity=contract.execution_identity,
        wrapper=contract.wrapper, validate_receipt=contract.validate_receipt,
        trusted_receipt=contract.trusted_receipt, run=run_program, outcome=contract.outcome,
        receipt_schema="hypersearch.program-receipt/v1", worker="local-pinned-program", required=contract.SCHEMAS,
        exits={"PROGRAM_HOLDS": 0, "PROGRAM_FAILS": 1}, commands=("run-program", "replay-program"))


def execute(execution, **arguments):
    return study.execute(execution, route=program_route(), **arguments)


def main(args):
    return study.main(args, route=program_route())
