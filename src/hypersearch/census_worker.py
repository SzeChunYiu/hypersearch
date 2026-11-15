"""Private subprocess entry point: only the fixed bundled census verifier."""
import sys

from .census_contract import validate_bundle
from .census_verifier import census
from .study_json import MAX_BUNDLE_BYTES, encode, parse


def main():
    bundle = validate_bundle(parse(sys.stdin.buffer.read(MAX_BUNDLE_BYTES + 1)))
    question = bundle["question"]
    result = census({k: question[k] for k in ("moduli", "length", "short_max", "long_min")})
    sys.stdout.buffer.write(encode(result))


if __name__ == "__main__":
    main()
