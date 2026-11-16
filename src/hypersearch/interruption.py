"""Stopping a launch that holds a lease: SIGTERM, SIGINT and SIGHUP, and the launcher's own death.

While a lease is held and the outcome is not yet decided, a stop signal raises Interrupted in the
main thread. The route's clean-up then kills its child (for a program, the whole process group),
and the executor releases the task. Outside that window a stop is held until the step in progress
(acquiring, committing, exporting) has finished and is then delivered as it would have been without
the guard. Signals that were ignored when the guard started (as under nohup) stay ignored.
"""
from contextlib import contextmanager
import os
import signal
import sys
import threading

STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
PR_SET_PDEATHSIG = 1
_ACTIVE = None   # signal dispositions belong to the process, so at most one guard is in force


class Interrupted(BaseException):
    """A stop signal ended an attempt. Not an Exception, so no handler of failures turns it into an outcome."""

    def __init__(self, signum, result=None):
        self.signum, self.name, self.result = signum, signal.Signals(signum).name, result
        super().__init__(self.name)


class Guard:
    def __init__(self):
        self.live = False      # raise at once, rather than hold the stop
        self.received = None  # the first stop signal received
        self.raised = False    # Interrupted has been raised; later stops are absorbed by the clean-up

    def _take(self):
        self.live, self.raised = False, True
        raise Interrupted(self.received)

    def handle(self, signum, frame):
        if self.received is None:
            self.received = signum
        if self.live and not self.raised:
            self._take()

    @contextmanager
    def armed(self):
        """The window in which a stop interrupts: lease held, outcome undecided."""
        if self.received is not None and not self.raised:
            self._take()
        self.live = not self.raised
        try:
            yield
        finally:
            self.live = False


class _Inactive:
    @contextmanager
    def armed(self):
        yield


@contextmanager
def stopping():
    """Install the stop handlers for one leased attempt. Only the main thread can, and only once."""
    global _ACTIVE
    if threading.current_thread() is not threading.main_thread() or _ACTIVE is not None:
        yield _Inactive()
        return
    guard = Guard()
    previous = {}
    try:
        for number in STOP_SIGNALS:
            current = signal.getsignal(number)
            if current != signal.SIG_IGN:
                previous[number] = signal.SIG_DFL if current is None else current
                signal.signal(number, guard.handle)
        _ACTIVE = guard
        yield guard
    finally:
        _ACTIVE = None
        for number, handler in previous.items():
            signal.signal(number, handler)
        if guard.received is not None and not guard.raised:
            signal.raise_signal(guard.received)   # held until now; the default ends the process here


@contextmanager
def held():
    """Hold a stop while a child is being started, so that it is taken once the child can be killed."""
    guard = _ACTIVE
    if guard is None or not guard.live or threading.current_thread() is not threading.main_thread():
        yield
        return
    guard.live = False
    try:
        yield
    finally:
        guard.live = not guard.raised
    if guard.received is not None and not guard.raised:
        guard._take()


def parent_death():
    """A preexec step that has the kernel SIGKILL the child when the thread that started it ends.

    Linux only (prctl PR_SET_PDEATHSIG); None where it is not available. It covers the child itself,
    not processes the child starts. A launcher that died before the step ran is caught by its
    parent id having changed.
    """
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        prctl = ctypes.CDLL(None, use_errno=True).prctl
    except (ImportError, OSError, AttributeError):
        return None
    prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    prctl.restype = ctypes.c_int
    parent = os.getpid()

    def arm():
        if prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "cannot set the parent-death signal")
        if os.getppid() != parent:
            os.kill(os.getpid(), signal.SIGKILL)
    return arm
