"""Validate completed bounded-verifier output; failures are never refutations."""
from .study_json import artifact_bytes, digest, encode, fields, integer, parse


def _blocks(blocks, certificate, count):
    if type(blocks) is not list or len(blocks) != count:
        raise ValueError("invalid packing block count")
    seen = set()
    sequence, moduli = certificate["sequence"], certificate["moduli"]
    for block in blocks:
        if type(block) is not list or not block:
            raise ValueError("empty or malformed zero-sum block")
        for i in block:
            integer(i, 0, len(sequence) - 1)
            if i in seen:
                raise ValueError("packing repeats an occurrence")
            seen.add(i)
        if any(sum(sequence[i][j] for i in block) % n for j, n in enumerate(moduli)):
            raise ValueError("reported block is not zero-sum")


def verification(value, bundle):
    question = bundle["question"]
    certificate = parse(artifact_bytes(bundle["artifacts"]["certificate"]), 65536)
    if type(value) is not dict or type(value.get("verified")) is not bool:
        raise ValueError("malformed verifier output")
    verified, length = value["verified"], question["length"]
    if question["adapter"] == "ordinary-witness":
        common = "verified scope moduli subsets_checked"
        fields(value, common + (" lower_bound evidence_kind formal_proof novelty_assessed" if verified
                                else " reason counterexample_indices"))
        if value["scope"] != "finite_group_lower_bound":
            raise ValueError("wrong ordinary verifier scope")
        if not verified:
            if value["reason"] != "nonempty_zero_sum_subset":
                raise ValueError("unsupported rejection reason")
            _blocks([value["counterexample_indices"]], certificate, 1)
        elif value["evidence_kind"] != "independently_recomputed_computational_witness":
            raise ValueError("unsupported evidence kind")
    else:
        common = ("verified scope moduli k sequence_length maximum_disjoint_zero_sum_subsequences "
                  "maximal_packing_indices subsets_checked packing_transitions certificate_sha256 "
                  "formal_proof novelty_assessed evidence_kind")
        fields(value, common + (" lower_bound" if verified else " reason counterexample_indices"))
        if (value["scope"] != "finite_group_multiwise_lower_bound" or type(value["k"]) is not int
                or value["k"] != question["k"] or type(value["sequence_length"]) is not int
                or value["sequence_length"] != length):
            raise ValueError("wrong multiwise task binding")
        maximum = value["maximum_disjoint_zero_sum_subsequences"]
        integer(maximum, 0, length)
        if verified != (maximum < question["k"]):
            raise ValueError("packing verdict mismatch")
        _blocks(value["maximal_packing_indices"], certificate, maximum)
        integer(value["packing_transitions"], 0, 3**length)
        if (value["certificate_sha256"] != digest(encode(certificate))
                or value["evidence_kind"] != "exact_bounded_computational_verification"):
            raise ValueError("wrong certificate or evidence identity")
        if not verified:
            if value["reason"] != "at_least_k_disjoint_zero_sum_subsequences":
                raise ValueError("unsupported rejection reason")
            _blocks(value["counterexample_indices"], certificate, question["k"])
    if value["moduli"] != question["moduli"] or any(type(n) is not int for n in value["moduli"]):
        raise ValueError("wrong group in verifier output")
    integer(value["subsets_checked"], 0, (1 << length) - 1)
    if verified or question["adapter"] == "multiwise-witness":
        if value["subsets_checked"] != (1 << length) - 1:
            raise ValueError("incomplete subset coverage")
        if value["formal_proof"] is not False or value["novelty_assessed"] is not False:
            raise ValueError("unsupported proof or novelty assertion")
    if verified and (type(value["lower_bound"]) is not int or value["lower_bound"] != length + 1):
        raise ValueError("unsupported lower bound")
    return {"status": "VERIFIED_WITNESS" if verified else "REFUTED_WITNESS", "verification": value}


def outcome(value, bundle):
    fields(value, "status verification")
    if type(value["status"]) is not str:
        raise ValueError("invalid outcome status")
    if value["status"] in {"VERIFIED_WITNESS", "REFUTED_WITNESS"}:
        if verification(value["verification"], bundle) != value:
            raise ValueError("inconsistent outcome status")
    elif value["status"] not in {"EXECUTION_FAILED", "INCOMPLETE"} or value["verification"] is not None:
        raise ValueError("unsupported execution outcome")
    return value
