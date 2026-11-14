"""Bounded exact checks for multiwise Davenport lower-bound witnesses.

For a sequence S, D_k(G) > len(S) follows when S has fewer than k pairwise
DISJOINT nonempty zero-sum subsequences. Positions preserve multiplicity.
Definition: Freeze and Schmid, https://arxiv.org/abs/0905.4248 .
This is a finite computation, not formal proof, novelty review or an upper bound.
The length cap excludes large frontier witnesses even in supported groups.
"""
from hashlib import sha256
import json
from math import prod

SCHEMA = "hypersearch.multiwise-certificate/v1"
MAX_LENGTH = 16
MAX_ORDER = 1_000_000


def _moduli(value):
    if type(value) is not list or not 1 <= len(value) <= 3:
        raise ValueError("moduli must be a list of one to three integers")
    if any(type(n) is not int or not 2 <= n <= MAX_ORDER for n in value):
        raise ValueError("moduli must be integers in [2, 1000000]")
    if prod(value) > MAX_ORDER:
        raise ValueError("group order exceeds 1000000")
    return tuple(value)


def _k(value):
    if type(value) is not int or not 1 <= value <= 16:
        raise ValueError("k must be an integer in [1, 16]")
    return value


def verify_certificate(certificate, *, expected_moduli=None, expected_k=None):
    """Recompute the exact zero-sum packing number of a <=16-term sequence.

    Closed input fields deliberately contain no claimed verdict. The task runner
    must bind its frozen group and k using expected_moduli and expected_k. Digest
    identifies input bytes under canonical JSON; it does not authenticate them.
    Malformed or out-of-cap inputs raise ValueError; no partial PASS is returned.
    """
    if type(certificate) is not dict or set(certificate) != {"schema", "moduli", "k", "sequence"}:
        raise ValueError("unexpected multiwise certificate schema")
    if certificate["schema"] != SCHEMA:
        raise ValueError("unsupported multiwise certificate schema")
    ns = _moduli(certificate["moduli"])
    k = _k(certificate["k"])
    if expected_moduli is not None and ns != _moduli(expected_moduli):
        raise ValueError("group does not match frozen task")
    if expected_k is not None and k != _k(expected_k):
        raise ValueError("k does not match frozen task")
    sequence = certificate["sequence"]
    if type(sequence) is not list or len(sequence) > MAX_LENGTH:
        raise ValueError("sequence must contain at most 16 terms")
    for term in sequence:
        if type(term) is not list or len(term) != len(ns):
            raise ValueError("term dimension does not match group")
        if any(type(x) is not int or not 0 <= x < n for x, n in zip(term, ns)):
            raise ValueError("coordinates must be canonical integers")

    size = 1 << len(sequence)
    zero = (0,) * len(ns)
    sums = [zero] * size
    is_zero = bytearray(size)
    for mask in range(1, size):
        bit = mask & -mask
        term = sequence[bit.bit_length() - 1]
        sums[mask] = tuple((a + b) % n for a, b, n in zip(sums[mask ^ bit], term, ns))
        is_zero[mask] = sums[mask] == zero

    # Every packing either omits the least position, or has exactly one block
    # containing it. Enumerating both cases makes this recurrence exhaustive.
    best = bytearray(size)
    chosen = [0] * size
    transitions = 0
    for mask in range(1, size):
        bit = mask & -mask
        rest = mask ^ bit
        best[mask] = best[rest]
        sub = rest
        while True:
            block = sub | bit
            transitions += 1
            if is_zero[block]:
                count = 1 + best[mask ^ block]
                if count > best[mask]:
                    best[mask], chosen[mask] = count, block
                    if count == mask.bit_count():
                        break  # absolute upper bound: each block is nonempty
            if not sub:
                break
            sub = (sub - 1) & rest

    mask = size - 1
    packing = []
    while mask:
        block = chosen[mask]
        if block:
            packing.append([i for i in range(len(sequence)) if block & (1 << i)])
            mask ^= block
        else:
            mask ^= mask & -mask
    verified = best[-1] < k
    receipt = {
        "verified": verified,
        "scope": "finite_group_multiwise_lower_bound",
        "moduli": list(ns), "k": k,
        "sequence_length": len(sequence),
        "maximum_disjoint_zero_sum_subsequences": best[-1],
        "maximal_packing_indices": packing,
        "subsets_checked": size - 1, "packing_transitions": transitions,
        "certificate_sha256": sha256(json.dumps(certificate, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        "formal_proof": False, "novelty_assessed": False,
        "evidence_kind": "exact_bounded_computational_verification",
    }
    if verified:
        receipt["lower_bound"] = len(sequence) + 1
    else:
        receipt["reason"] = "at_least_k_disjoint_zero_sum_subsequences"
        receipt["counterexample_indices"] = packing[:k]
    return receipt
