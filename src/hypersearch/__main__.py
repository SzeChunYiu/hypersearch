"""Module entry point. The launch check runs before any non-frozen import."""
import os
import sys

_PINNED = {"run-study", "replay-study", "register-review", "grant-review", "submit-review", "recover-review"}


def _refuse(reason):
    print("hypersearch: " + reason, file=sys.stderr)
    sys.stderr.flush()
    os._exit(2)  # -i or PYTHONINSPECT would otherwise replace this exit code


if len(sys.argv) > 1 and sys.argv[1] in _PINNED:
    if sys.flags.inspect or os.environ.get("PYTHONINSPECT"):
        _refuse("launch without -i or PYTHONINSPECT")
    if not (sys.flags.safe_path and sys.flags.no_site and sys.dont_write_bytecode and sys.pycache_prefix):
        _refuse("launch with -B -S -P -X pycache_prefix=<new empty directory>")
    _here = os.path.realpath(os.getcwd())
    _source = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if _here != _source and any(os.path.realpath(entry or ".") == _here for entry in sys.path):
        _refuse("import path reaches outside the pinned core and interpreter library")

try:
    from .cli import main
    code = main()
except Exception as error:  # exit 1 means a completed refutation; a crash must never read as one
    import traceback
    traceback.print_exc()
    print(f"hypersearch: internal failure: {type(error).__name__}: {error}", file=sys.stderr)
    code = 2
raise SystemExit(code)
