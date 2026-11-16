"""Who holds a lease, whether that process still runs, and the abandon-attempt command.

A holder is a process id, the process's start time in clock ticks since boot, the kernel's boot id,
the process-id namespace and the host name. A process id alone is reused; with the start time and the
boot id it names one process for the life of a host, and only inside its own process-id namespace. Read from /proc, so Linux only: elsewhere nothing is recorded and
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


def _namespace():
    """This process's process-id namespace, read through a /proc that belongs to it."""
    if os.readlink(PROC / "self") != str(os.getpid()):
        raise OSError("/proc was mounted from another process-id namespace")
    return os.readlink(PROC / "self/ns/pid")


def _exists(pid):
    """False only when the kernel says no such process; /proc can hide another user's processes."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def identity(pid=None):
    """The holder record of a process (this one by default), or None where it cannot be read."""
    pid = os.getpid() if pid is None else pid
    try:
        namespace = _namespace()                # first: it proves /proc numbers processes as we do
        stat = _stat(pid)
        boot = _boot()
    except (OSError, ValueError, IndexError):
        return None
    host = socket.gethostname()
    if stat is None or not boot or not namespace or not host.strip():
        return None                             # nothing recorded: the lease can only expire
    return {"pid": pid, "started": stat[1], "boot": boot, "pidns": namespace, "host": host}


def state(holder):
    """"alive", "dead" or "unknown" (another host or process-id namespace, a process /proc hides, or no
    /proc to read). Only "dead" frees a lease."""
    if holder["host"] != socket.gethostname():
        return "unknown"
    try:
        boot = _boot()
        namespace = _namespace()
    except OSError:
        return "unknown"
    if boot != holder["boot"]:
        return "dead"                           # the host was restarted since the lease was granted
    if namespace != holder.get("pidns"):
        return "unknown"                        # the same number names another process there
    try:
        stat = _stat(holder["pid"])
    except (OSError, ValueError, IndexError):
        return "unknown"
    if stat is None:
        return "unknown" if _exists(holder["pid"]) else "dead"   # hidden (hidepid) is not gone
    if stat[0] in ("Z", "X") or stat[1] != holder["started"]:
        return "dead"                           # exited but not yet reaped, or the id was reused
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
