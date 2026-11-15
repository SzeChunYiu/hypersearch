import sys

try:
    from .cli import main
    code = main()
except Exception as error:  # exit 1 means a completed refutation; a crash must never read as one
    print(f"hypersearch: internal failure: {type(error).__name__}: {error}", file=sys.stderr)
    code = 2
raise SystemExit(code)
