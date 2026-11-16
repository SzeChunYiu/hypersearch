"""Who holds a lease, whether that process still runs, and the abandon-attempt command.

A holder is a process id, the process's start time in clock ticks since boot, the kernel's boot id
and the host name. A process id alone is reused; with the start time and the boot id it names one
process for the life of a host. Read from /proc, so Linux only: elsewhere nothing is recorded and
nothing can be abandoned, and a stranded lease expires as before.
"""
import json
import os
from pathlib import Path
import socket

from .store import Store

PROC = Path("/proc")


def _stat(pid):
    """(state, start time) of a process, or None when it does not exist."""
    try:
        raw = (PROC / str(pid) / "stat").read_text(encoding="ascii", errors="replace")
    except (FileNotFoundError, ProcessLookupError):
        return None
    fields = raw[raw.rindex(")") + 2:].split()   # the command name may contain spaces and parentheses
    return fields[0], int(fields[19])           # fields 3 and 22 of proc_pid_stat(5)


def _boot():
    return (PROC / "sys/kernel/random/boot_id").read_text(encoding="ascii").strip()


def identity(pid=None):
    """The holder record of a process (this one by default), or None where it cannot be read."""
    pid = os.getpid() if pid is None else pid
    try:
        stat = _stat(pid)
        boot = _boot()
    except (OSError, ValueError, IndexError):
        return None
    if stat is None:
        return None
    return {"pid": pid, "started": stat[1], "boot": boot, "host": socket.gethostname()}


def state(holder):
    """"alive", "dead" or "unknown" (another host, or no /proc to read). Only "dead" frees a lease."""
    if holder["host"] != socket.gethostname():
        return "unknown"
    try:
        boot = _boot()
    except OSError:
        return "unknown"
    if boot != holder["boot"]:
        return "dead"                           # the host was restarted since the lease was granted
    try:
        stat = _stat(holder["pid"])
    except (OSError, ValueError, IndexError):
        return "unknown"
    if stat is None or stat[0] in ("Z", "X") or stat[1] != holder["started"]:
        return "dead"                           # gone, exited but not yet reaped, or the id was reused
    return "alive"


def main(args):
    """abandon-attempt: free the lease of a launcher that died without releasing it. Never deletes."""
    store = Store.existing(args.db)
    record = store.abandon(args.task, args.fence, args.reason, holder_state=state)
    after = store.snapshot()
    task = next(t for t in after["tasks"] if t["id"] == args.task)
    print(json.dumps({"execution": "abandoned", **record, "budget": after["budget"], "task_state": task["state"]},
                     sort_keys=True, separators=(",", ":")))
    return 0
