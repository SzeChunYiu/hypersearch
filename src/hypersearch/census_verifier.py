"""Exhaustive bounded census of sequences avoiding zero-sums of given lengths.

For a finite abelian group G, a length n, and bounds m and optionally q, count
the multisets of n elements of G that have no nonempty zero-sum subsequence of
length at most m and, if q is given, none of length at least q.

Completeness. "No zero-sum subsequence of length <= m" is inherited by every
subsequence, so every such multiset of size d + 1 extends one of size d. Each
multiset is visited once as a nondecreasing sequence of element codes; a branch
is cut exactly when the new term closes a zero-sum of length <= m. The long
condition is not inherited and is tested only on complete sequences.

This is one implementation of a finite computation. It is not a formal proof,
and a count of zero is only as trustworthy as this code.
"""
from math import prod

VERIFIER = "hypersearch.zero-sum-census/v1"
MAX_ORDER = 64
MAX_LENGTH = 20


def validate_question(question):
    """Admit group and bounds without enumerating anything."""
    if type(question) is not dict or set(question) != {"moduli", "length", "short_max", "long_min"}:
        raise ValueError("unexpected census question fields")
    moduli = question["moduli"]
    if type(moduli) is not list or not 1 <= len(moduli) <= 3:
        raise ValueError("moduli must be a list of one to three integers")
    if any(type(n) is not int or n < 2 for n in moduli) or prod(moduli) > MAX_ORDER:
        raise ValueError("census group order must be at most 64")
    length, short, long = question["length"], question["short_max"], question["long_min"]
    if type(length) is not int or not 1 <= length <= MAX_LENGTH:
        raise ValueError("census length must be an integer in [1, 20]")
    if type(short) is not int or not 1 <= short <= length:
        raise ValueError("short_max must be an integer in [1, length]")
    if long is not None:
        if type(long) is not int or not short < long <= length:
            raise ValueError("long_min must be null or an integer in (short_max, length]")
        if length - long > short - 1:
            # A zero-sum of length n - j is a deletion of j terms summing to the total;
            # only sub-sums of fewer than short_max terms are tracked.
            raise ValueError("long_min is too far below length for this short_max")
    return tuple(moduli), length, short, long


def _tables(moduli):
    order = prod(moduli)
    def decode(code):
        out = []
        for n in reversed(moduli):
            out.append(code % n); code //= n
        return tuple(reversed(out))
    def encode(point):
        code = 0
        for x, n in zip(point, moduli):
            code = code * n + x
        return code
    points = [decode(c) for c in range(order)]
    add = [[encode(tuple((a + b) % n for a, b, n in zip(points[x], points[y], moduli))) for y in range(order)]
           for x in range(order)]
    negative = [encode(tuple((-a) % n for a, n in zip(points[x], moduli))) for x in range(order)]
    chunks = (order + 7) // 8
    # shift[x][i][byte]: the set {y + x : y in the i-th byte of a bitmask}, as a bitmask.
    shift = [[[sum(1 << add[x][8 * i + b] for b in range(8) if byte >> b & 1 and 8 * i + b < order)
               for byte in range(256)] for i in range(chunks)] for x in range(order)]
    return order, points, add, negative, shift


def census(question):
    """Count the sequences described above. Deterministic; no early exit on the first hit."""
    moduli, length, short, long = validate_question(question)
    order, points, add, negative, shift = _tables(moduli)
    levels = [0] * (length + 1)
    count, example = 0, None
    chosen = []

    def translate(mask, table):
        out, i = 0, 0
        while mask:
            out |= table[i][mask & 255]
            mask >>= 8; i += 1
        return out

    def extend(reach, start, total):
        # reach[j]: sums of j-term subsequences of the current sequence, j < short.
        nonlocal count, example
        depth = len(chosen)
        levels[depth] += 1
        if depth == length:
            if long is not None and any(reach[j] >> total & 1 for j in range(length - long + 1)):
                return  # deleting those j terms leaves a zero-sum of length >= long
            count += 1
            if example is None:
                example = [list(points[x]) for x in chosen]
            return
        forbidden = 0
        for mask in reach:
            forbidden |= mask
        for x in range(start, order):
            if forbidden >> negative[x] & 1:
                continue  # some j < short earlier terms sum to -x: a zero-sum of length j + 1
            table = shift[x]
            grown = [reach[0]] + [reach[j] | translate(reach[j - 1], table) for j in range(1, short)]
            chosen.append(x)
            extend(grown, x, add[total][x])
            chosen.pop()

    extend([1] + [0] * (short - 1), 0, 0)
    return {"scope": "finite_group_zero_sum_census", "moduli": list(moduli), "length": length,
            "short_max": short, "long_min": long, "count": count, "levels": levels, "example": example,
            "evidence_kind": "exhaustive_bounded_enumeration", "formal_proof": False,
            "novelty_assessed": False}


def offending_subsequence(sequence, moduli, short, long):
    """Independent subset check of one sequence: indices of a forbidden zero-sum, or None."""
    size = len(sequence)
    zero = (0,) * len(moduli)
    sums = [zero] * (1 << size)
    for mask in range(1, 1 << size):
        bit = mask & -mask
        term = sequence[bit.bit_length() - 1]
        sums[mask] = tuple((a + b) % n for a, b, n in zip(sums[mask ^ bit], term, moduli))
        if sums[mask] == zero:
            terms = mask.bit_count()
            if terms <= short or (long is not None and terms >= long):
                return [i for i in range(size) if mask >> i & 1]
    return None
