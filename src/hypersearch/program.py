"""Frozen consumer-program tasks on the same Store, lease, receipt and export path as studies."""
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

from . import program_contract as contract
from . import study
from .interruption import Interrupted, held, parent_death
from .study_json import artifact_bytes, encode, parse
from .study_usage import Meter, feed, reap

# The bytes are compiled as source text whatever they look like, so an archive, bytecode or an
# encoding declaration cannot change what runs. One expression: it executes in the real __main__
# module and adds no name to it.
BOOTSTRAP = "exec(compile(open(__import__('sys').argv[1], encoding='ascii').read(), 'program.py', 'exec'))"


def run_program(bundle, core, meter=None):
    """Run the bundled program bytes, never the consumer's working file, in an isolated interpreter.

    Isolation is from ambient imports, environment and bytecode. It is not a security sandbox:
    the program runs with the operator's file and network access, and a process it moves out of
    its process group outlives the timeout. A stop signal (see interruption.py) ends the run with
    the group killed; on Linux the program also dies with the thread that started it.
    """
    limits = bundle["limits"]
    memory = limits["memory_megabytes"] * 1048576
    meter = meter or Meter()
    orphaned = parent_death()

    def confine():
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if orphaned is not None:
            orphaned()

    raw = artifact_bytes(bundle["artifacts"]["program"])
    contract.source_text(raw)
    # A process that left the group can still write here; that must not turn a result into a failure.
    with tempfile.TemporaryDirectory(prefix="hypersearch-program-", ignore_cleanup_errors=True) as work:
        path = Path(work, "program.py")
        path.write_bytes(raw)
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            started = time.monotonic()
            child, timed_out, stopped = None, False, False
            try:  # the input is at most 4 KiB, so writing it cannot block; wait4 gives the child's own usage
                with held():  # a stop while it starts is taken once there is a group to kill
                    child = subprocess.Popen([sys.executable, "-B", "-I", "-S", "-c", BOOTSTRAP, str(path)],
                                             stdin=subprocess.PIPE, stdout=out,
                                             stderr=err, cwd=work, env={"PATH": os.defpath}, start_new_session=True,
                                             preexec_fn=confine)
                feed(child, encode(bundle["question"]["arguments"]))
                reap(child, meter, started, limits["timeout_seconds"])
            except subprocess.TimeoutExpired:
                timed_out = True
            except Interrupted:  # re-raised after the finally below; a reap race must not replace it
                stopped = True
                raise
            finally:  # also when a stop signal interrupted the wait
                if child is not None:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)  # the program's process group, not what left it
                    except ProcessLookupError:
                        pass
                    try:
                        reap(child, meter, started)
                    except ChildProcessError:  # already reaped (after a timeout or a stop): never a failure
                        if not (timed_out or stopped):
                            raise
            if timed_out:
                return {"status": "INCOMPLETE", "verification": None}, "program timeout"
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
