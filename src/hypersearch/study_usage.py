"""Resource usage of the one child process a frozen route waits for.

Printed with the command result only. It describes the host, not the question, so it is never
part of a receipt and never compared by a replay. Integers only, like every other number here.
"""
from contextlib import contextmanager
import os
import resource
import subprocess
import sys
import time

_UNIT = 1024 if sys.platform == "darwin" else 1  # ru_maxrss is bytes on macOS and kilobytes on Linux


class Meter:
    """What one execution's child used: zeros and null until a child has been waited for."""

    def __init__(self):
        self.wall = self.cpu = 0.0
        self.peak = None

    def report(self):
        return {"wall_milliseconds": round(self.wall * 1000), "cpu_milliseconds": round(self.cpu * 1000),
                "max_rss_kilobytes": self.peak}


@contextmanager
def waited_children(meter):
    """Measure a call that starts one child and waits for it, such as subprocess.run.

    The counters are those of every child this process has waited for. Another child reaped
    meanwhile is therefore included, and the peak is a high-water mark over all of them: it is
    reported only when this call raised it, and is unknown (null) otherwise.
    """
    started, before = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        yield
    finally:
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        meter.wall = time.monotonic() - started
        meter.cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
        meter.peak = after.ru_maxrss // _UNIT if after.ru_maxrss > before.ru_maxrss else None


def feed(child, data):
    """Give a child its whole input and close the pipe. A child that never reads it is not an error."""
    for step in (lambda: child.stdin.write(data), child.stdin.close):
        try:
            step()
        except BrokenPipeError:
            pass


def reap(child, meter, started, timeout=None):
    """Wait for a subprocess.Popen child with wait4 and set its return code.

    wait4 reports that child alone, with the descendants it waited for itself, so the peak is its
    own. With a timeout this raises subprocess.TimeoutExpired and leaves the child running; call
    again without one once it has been killed. A child that something else reaped, as when SIGCHLD
    is ignored, has no known exit status: that raises ChildProcessError and is never read as exit 0.
    """
    delay = 0.0005
    while child.returncode is None:
        try:
            pid, status, used = os.wait4(child.pid, 0 if timeout is None else os.WNOHANG)
        except ChildProcessError:
            child.wait()  # settles the object the way subprocess does; the caller still gets the error
            raise
        if pid == child.pid:
            child.returncode = os.waitstatus_to_exitcode(status)
            meter.wall, meter.cpu = time.monotonic() - started, used.ru_utime + used.ru_stime
            meter.peak = used.ru_maxrss // _UNIT
            return
        remaining = started + timeout - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(child.args, timeout)
        delay = min(delay * 2, remaining, 0.05)
        time.sleep(delay)
