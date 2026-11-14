"""Private subprocess entry point: only fixed bundled certificate verifiers."""
import sys

from .math_adapter import verify_certificate as ordinary
from .multiwise import verify_certificate as multiwise
from .study_contract import validate_bundle
from .study_json import MAX_BUNDLE_BYTES, artifact_bytes, encode, parse


def main():
    bundle = validate_bundle(parse(sys.stdin.buffer.read(MAX_BUNDLE_BYTES + 1)))
    question = bundle["question"]
    certificate = parse(artifact_bytes(bundle["artifacts"]["certificate"]), 65536)
    if question["adapter"] == "ordinary-witness":
        result = ordinary(certificate, expected_moduli=question["moduli"])
    else:
        result = multiwise(certificate, expected_moduli=question["moduli"], expected_k=question["k"])
    sys.stdout.buffer.write(encode(result))


if __name__ == "__main__":
    main()
