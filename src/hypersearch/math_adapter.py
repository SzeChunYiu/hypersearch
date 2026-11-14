"""Bounded zero-sum witness search; independent finite certificate checking.

No solver result proves an upper bound, equality, novelty, or a general theorem.
The verifier deliberately uses indexed subset enumeration, not the search's
incremental reachable-sums algorithm. Both remain ordinary Python computations.
"""

from hashlib import sha256
from itertools import product
import json
from math import prod

MAX_ORDER = 64
MAX_LENGTH = 16
MAX_STEPS = 100_000


def _moduli(value):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 3:
        raise ValueError("moduli must contain one to three integers")
    if any(type(n) is not int or not 2 <= n <= MAX_ORDER for n in value):
        raise ValueError("each modulus must be an integer between 2 and 64")
    if prod(value) > MAX_ORDER:
        raise ValueError("group order exceeds 64")
    return tuple(value)


def _digest(certificate):
    payload = {k: v for k, v in certificate.items() if k != "sha256"}
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def validate_search_inputs(moduli, max_steps):
    """Validate bounded adapter inputs without search or persistent effects."""
    ns = _moduli(moduli)
    if type(max_steps) is not int or not 1 <= max_steps <= MAX_STEPS:
        raise ValueError("max_steps must be an integer between 1 and 100000")
    return ns


def search(moduli, max_steps=10_000):
    """Return a deterministic witness certificate within a candidate-step cap.

    Nondecreasing sequences remove permutation duplicates, not repeated terms.
    A truncated search may still produce a valid lower-bound witness.
    """
    ns = validate_search_inputs(moduli, max_steps)
    zero = (0,) * len(ns)
    elements = [g for g in product(*(range(n) for n in ns)) if g != zero]
    best = []
    steps = 0
    depth_cap_reached = False

    def visit(sequence, reachable, first):
        nonlocal best, steps, depth_cap_reached
        if len(sequence) > len(best):
            best = list(sequence)
        if len(sequence) == MAX_LENGTH:
            depth_cap_reached = True
            return
        for index in range(first, len(elements)):
            if steps >= max_steps:
                return
            steps += 1
            g = elements[index]
            if tuple((-x) % n for x, n in zip(g, ns)) in reachable:
                continue
            expanded = reachable | {g} | {
                tuple((x + y) % n for x, y, n in zip(s, g, ns))
                for s in reachable
            }
            visit(sequence + [g], expanded, index)

    visit([], set(), 0)
    certificate = {
        "version": 1,
        "kind": "zero_sum_free_witness",
        "moduli": list(ns),
        "sequence": [list(g) for g in best],
        "lower_bound": len(best) + 1,
        "search": {"steps": steps, "max_steps": max_steps,
                   "step_cap_reached": steps >= max_steps,
                   "length_cap_reached": depth_cap_reached},
    }
    certificate["sha256"] = _digest(certificate)
    return certificate


def verify_certificate(certificate, *, expected_moduli=None):
    """Check a certificate independently; malformed inputs raise ValueError.

    The digest detects accidental modification, not malicious authorship. The
    evidence rests on recomputation. Search telemetry is never proof evidence.
    Independence here means a distinct algorithm, not an independent team or
    formal proof. Task runners must supply their frozen expected_moduli.
    """
    fields = {"version", "kind", "moduli", "sequence", "lower_bound",
              "search", "sha256"}
    if type(certificate) is not dict or set(certificate) != fields:
        raise ValueError("unexpected certificate schema")
    if type(certificate["version"]) is not int or certificate["version"] != 1:
        raise ValueError("unsupported certificate version")
    if certificate["kind"] != "zero_sum_free_witness":
        raise ValueError("unsupported certificate kind")
    ns = _moduli(certificate["moduli"])
    if expected_moduli is not None and ns != _moduli(expected_moduli):
        raise ValueError("certificate group does not match the frozen task")
    sequence = certificate["sequence"]
    if type(sequence) is not list or len(sequence) > MAX_LENGTH:
        raise ValueError("sequence must be a list of at most 16 terms")
    for term in sequence:
        if type(term) is not list or len(term) != len(ns):
            raise ValueError("term dimension does not match group")
        if any(type(x) is not int or not 0 <= x < n for x, n in zip(term, ns)):
            raise ValueError("coordinates must be canonical integers")
    bound = certificate["lower_bound"]
    if type(bound) is not int or bound != len(sequence) + 1:
        raise ValueError("claimed bound does not match witness length")
    telemetry = certificate["search"]
    if type(telemetry) is not dict or set(telemetry) != {
            "steps", "max_steps", "step_cap_reached", "length_cap_reached"}:
        raise ValueError("invalid search telemetry schema")
    if (type(telemetry["steps"]) is not int
            or type(telemetry["max_steps"]) is not int
            or not 0 <= telemetry["steps"] <= telemetry["max_steps"] <= MAX_STEPS
            or telemetry["max_steps"] < 1
            or type(telemetry["step_cap_reached"]) is not bool
            or type(telemetry["length_cap_reached"]) is not bool):
        raise ValueError("invalid search telemetry values")
    if type(certificate["sha256"]) is not str or certificate["sha256"] != _digest(certificate):
        raise ValueError("certificate digest mismatch")

    # Independent brute-force verification includes multiplicities by indexing
    # positions. The empty subset is intentionally excluded.
    checked = 0
    for mask in range(1, 1 << len(sequence)):
        checked += 1
        indices = [i for i in range(len(sequence)) if mask & (1 << i)]
        sums = [sum(sequence[i][j] for i in indices) % n
                for j, n in enumerate(ns)]
        if not any(sums):
            return {"verified": False, "scope": "finite_group_lower_bound",
                    "moduli": list(ns), "reason": "nonempty_zero_sum_subset",
                    "counterexample_indices": indices, "subsets_checked": checked}
    return {"verified": True, "scope": "finite_group_lower_bound",
            "moduli": list(ns), "lower_bound": len(sequence) + 1,
            "subsets_checked": checked,
            "evidence_kind": "independently_recomputed_computational_witness",
            "formal_proof": False, "novelty_assessed": False}
