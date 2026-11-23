"""Read-only exact integer & odd-modular left-kernel Farkas certificate checker.

Verifies linear infeasibility certificates under schema
``hypersearch.linear-infeasibility-certificate/v1`` using exact Python integer
arithmetic and zero third-party dependencies.

Mathematical soundness:
- Exact integer mode (``modulus is None``): if integer row vector ``u`` satisfies
  ``u @ M == 0`` and ``u @ b == g != 0``, then ``M x = b`` has no solution over
  any field whose characteristic does not divide ``g`` (nor over Q or Z).
- Odd-modular mode (``modulus`` an odd integer >= 3): if ``u @ M == 0 (mod m)``
  and ``u @ b != 0 (mod m)``, then ``M x == b (mod m)`` has no solution over
  ``Z / m Z`` (and over ``F_m`` whenever ``m`` is prime).

Primality testing uses deterministic 13-base Miller-Rabin (exact below
``3,317,044,064,679,887,385,961,981``, Sorenson & Webster 2015) paired with
small-prime trial division and bounded Pollard-Brent factorization.
"""
from __future__ import annotations

from math import gcd
from pathlib import Path

from .study_json import digest, encode, fields, integer, parse, sha, text

SCHEMA = "hypersearch.linear-infeasibility-certificate/v1"
VERIFIER = "hypersearch.linear-infeasibility/v1"

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 10_000
MAX_ROWS = 4096
MAX_COLS = 4096
MAX_ABS_ENTRY = 10 ** 60
MAX_MODULUS = 10 ** 18
MAX_POLLARD_STEPS = 20_000

# Deterministic Miller-Rabin bases for all integers < 3,317,044,064,679,887,385,961,981.
MR_BASES_13 = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
DETERMINISTIC_PRIMALITY_BOUND = 3_317_044_064_679_887_385_961_981


def _small_primes(limit: int = 1000) -> tuple[int, ...]:
    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[0:2] = b"\x00\x00"
    p = 2
    while p * p <= limit:
        if sieve[p]:
            sieve[p * p : limit + 1 : p] = b"\x00" * (((limit - p * p) // p) + 1)
        p += 1
    return tuple(i for i, flag in enumerate(sieve) if flag)


_TRIAL_PRIMES = _small_primes(1000)


def is_probable_prime_13(n: int) -> bool:
    """Deterministic 13-base Miller-Rabin primality test (exact below 3.317e24)."""
    if type(n) is not int or n < 2:
        return False
    for p in MR_BASES_13:
        if n == p:
            return True
        if n % p == 0:
            return False
    d, s = n - 1, 0
    while (d & 1) == 0:
        d >>= 1
        s += 1
    for a in MR_BASES_13:
        if a >= n:
            break
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _pollard_brent(n: int, *, max_steps: int = MAX_POLLARD_STEPS) -> int | None:
    """Bounded deterministic Pollard-Brent factor finder for composite odd n."""
    if n % 2 == 0:
        return 2
    steps = 0
    for c in (1, 2, 3, 5, 7, 11, 13):
        y, r, q, m = 2, 1, 1, 128
        g, ys, x = 1, 2, 2
        while g == 1 and steps < max_steps:
            x = y
            for _ in range(r):
                y = (y * y + c) % n
                steps += 1
                if steps >= max_steps:
                    break
            k = 0
            while k < r and g == 1 and steps < max_steps:
                ys = y
                bound = min(m, r - k)
                for _ in range(bound):
                    y = (y * y + c) % n
                    q = (q * abs(x - y)) % n
                    steps += 1
                    if steps >= max_steps:
                        break
                g = gcd(q, n)
                k += m
            r <<= 1
        if g == n:
            g = 1
            while g == 1 and steps < max_steps:
                ys = (ys * ys + c) % n
                g = gcd(abs(x - ys), n)
                steps += 1
        if 1 < g < n:
            return g
        if steps >= max_steps:
            break
    return None


def factor_positive_int(n: int, *, max_pollard_steps: int = MAX_POLLARD_STEPS) -> dict:
    """Factor a positive integer using trial division, 13-base MR, and bounded Pollard-Brent."""
    if type(n) is not int or n < 1:
        raise ValueError("positive integer required for factorization")
    rem = n
    factors: dict[int, int] = {}
    for p in _TRIAL_PRIMES:
        if p * p > rem:
            break
        while rem % p == 0:
            factors[p] = factors.get(p, 0) + 1
            rem //= p

    unfactored: list[int] = []
    stack = [rem] if rem > 1 else []
    budget = max_pollard_steps
    while stack:
        cur = stack.pop()
        if cur <= 1:
            continue
        if is_probable_prime_13(cur):
            if cur < DETERMINISTIC_PRIMALITY_BOUND:
                factors[cur] = factors.get(cur, 0) + 1
            else:
                unfactored.append(cur)
            continue
        if budget <= 0:
            unfactored.append(cur)
            continue
        step_slice = min(budget, max_pollard_steps)
        divisor = _pollard_brent(cur, max_steps=step_slice)
        budget = max(0, budget - min(step_slice, 1024))
        if divisor is None or divisor in (1, cur):
            unfactored.append(cur)
        else:
            stack.append(divisor)
            stack.append(cur // divisor)

    check_prod = 1
    for p, exp in factors.items():
        check_prod *= p ** exp
    for u in unfactored:
        check_prod *= u
    if check_prod != n:
        raise RuntimeError("factorization product invariant violated")

    primes = sorted(factors)
    unfactored.sort()
    return {
        "primes": primes,
        "prime_powers": [[p, factors[p]] for p in primes],
        "unfactored_cofactors": unfactored,
        "complete": not unfactored,
        "deterministic_primality_bound": DETERMINISTIC_PRIMALITY_BOUND,
    }


def _validate_modulus(modulus: int | None) -> int | None:
    if modulus is None:
        return None
    integer(modulus, 3, MAX_MODULUS)
    if modulus % 2 == 0:
        raise ValueError("modular certificate requires an odd modulus >= 3")
    return modulus


def _validate_system(num_rows: int, num_cols: int, rows: list, b: list, modulus: int | None) -> None:
    integer(num_rows, 1, MAX_ROWS)
    integer(num_cols, 1, MAX_COLS)
    _validate_modulus(modulus)
    if type(rows) is not list or len(rows) != num_rows:
        raise ValueError("rows must be a list of length num_rows")
    if type(b) is not list or len(b) != num_rows:
        raise ValueError("b must be a list of length num_rows")
    for r_idx, row in enumerate(rows):
        if type(row) is not list or len(row) > num_cols:
            raise ValueError(f"sparse row {r_idx} malformed")
        prev_col = -1
        for pair in row:
            if type(pair) is not list or len(pair) != 2:
                raise ValueError(f"sparse row {r_idx} entry must be [col, value]")
            col, val = pair
            integer(col, 0, num_cols - 1)
            if col <= prev_col:
                raise ValueError(f"sparse row {r_idx} columns must be strictly increasing")
            prev_col = col
            integer(val, -MAX_ABS_ENTRY, MAX_ABS_ENTRY)
            if val == 0:
                raise ValueError(f"sparse row {r_idx} must omit zero entries")
    for val in b:
        integer(val, -MAX_ABS_ENTRY, MAX_ABS_ENTRY)


def system_digest(
    num_rows: int,
    num_cols: int,
    rows: list[list[list[int]]],
    b: list[int],
    *,
    modulus: int | None = None,
) -> str:
    """Compute canonical SHA-256 digest binding linear system (M, b, modulus)."""
    _validate_system(num_rows, num_cols, rows, b, modulus)
    payload = {
        "b": b,
        "modulus": modulus,
        "num_cols": num_cols,
        "num_rows": num_rows,
        "rows": rows,
    }
    return digest(encode(payload))


def make_certificate_entry(
    *,
    entry_id: str,
    num_rows: int,
    num_cols: int,
    rows: list[list[list[int]]],
    b: list[int],
    u: list[int],
    modulus: int | None = None,
) -> dict:
    """Build a canonical certificate entry bound to its exact system digest."""
    text(entry_id)
    sys_sha = system_digest(num_rows, num_cols, rows, b, modulus=modulus)
    if type(u) is not list or len(u) != num_rows:
        raise ValueError("u must be a list of length num_rows")
    for val in u:
        integer(val, -MAX_ABS_ENTRY, MAX_ABS_ENTRY)
    return {
        "entry_id": entry_id,
        "num_rows": num_rows,
        "num_cols": num_cols,
        "rows": rows,
        "b": b,
        "u": u,
        "modulus": modulus,
        "system_sha256": sys_sha,
    }


def make_certificate_bundle(entries: list[dict]) -> dict:
    """Wrap canonical certificate entries into a schema-bound bundle."""
    if type(entries) is not list or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError("certificate bundle requires 1 to 10000 entries")
    return {"schema": SCHEMA, "entries": entries}


def verify_entry(
    entry: dict,
    *,
    expected_system_sha256: str | None = None,
    max_pollard_steps: int = MAX_POLLARD_STEPS,
) -> dict:
    """Independently verify one exact integer or odd-modular Farkas certificate entry."""
    fields(entry, "entry_id num_rows num_cols rows b u modulus system_sha256")
    text(entry["entry_id"])
    sha(entry["system_sha256"])
    if expected_system_sha256 is not None:
        sha(expected_system_sha256)

    num_rows = entry["num_rows"]
    num_cols = entry["num_cols"]
    rows = entry["rows"]
    b = entry["b"]
    u = entry["u"]
    modulus = entry["modulus"]

    computed_sha = system_digest(num_rows, num_cols, rows, b, modulus=modulus)
    if type(u) is not list or len(u) != num_rows:
        raise ValueError("u must be a list of length num_rows")
    for val in u:
        integer(val, -MAX_ABS_ENTRY, MAX_ABS_ENTRY)

    if entry["system_sha256"] != computed_sha:
        raise ValueError("entry system_sha256 does not match declared system (M, b, modulus)")
    if expected_system_sha256 is not None and computed_sha != expected_system_sha256:
        raise ValueError("declared system_sha256 does not match expected task system")

    u_m = [0] * num_cols
    for coeff, row in zip(u, rows):
        if coeff == 0:
            continue
        for col, val in row:
            u_m[col] += coeff * val

    g = sum(coeff * rhs for coeff, rhs in zip(u, b))
    entry_sha = digest(encode(entry))

    if modulus is None:
        nonzero_cols = [c for c, val in enumerate(u_m) if val != 0]
        if nonzero_cols:
            return {
                "entry_id": entry["entry_id"],
                "mode": "exact_integer",
                "verified": False,
                "reason": "nonzero_left_kernel_product",
                "first_nonzero_col": nonzero_cols[0],
                "g": g,
                "system_sha256": computed_sha,
                "entry_sha256": entry_sha,
            }
        if g == 0:
            return {
                "entry_id": entry["entry_id"],
                "mode": "exact_integer",
                "verified": False,
                "reason": "zero_rhs_dot_product",
                "g": 0,
                "system_sha256": computed_sha,
                "entry_sha256": entry_sha,
            }
        fac = factor_positive_int(abs(g), max_pollard_steps=max_pollard_steps)
        return {
            "entry_id": entry["entry_id"],
            "mode": "exact_integer",
            "verified": True,
            "g": g,
            "abs_g": abs(g),
            "exceptional_primes": fac["primes"],
            "prime_powers": fac["prime_powers"],
            "unfactored_cofactors": fac["unfactored_cofactors"],
            "factorization_complete": fac["complete"],
            "system_sha256": computed_sha,
            "entry_sha256": entry_sha,
        }

    nonzero_mod_cols = [c for c, val in enumerate(u_m) if (val % modulus) != 0]
    g_mod = g % modulus
    mod_prime = modulus < DETERMINISTIC_PRIMALITY_BOUND and is_probable_prime_13(modulus)
    if nonzero_mod_cols:
        return {
            "entry_id": entry["entry_id"],
            "mode": "odd_modular",
            "modulus": modulus,
            "modulus_is_prime": mod_prime,
            "verified": False,
            "reason": "nonzero_modular_left_kernel_product",
            "first_nonzero_col": nonzero_mod_cols[0],
            "g": g,
            "g_mod": g_mod,
            "system_sha256": computed_sha,
            "entry_sha256": entry_sha,
        }
    if g_mod == 0:
        return {
            "entry_id": entry["entry_id"],
            "mode": "odd_modular",
            "modulus": modulus,
            "modulus_is_prime": mod_prime,
            "verified": False,
            "reason": "zero_modular_rhs_dot_product",
            "g": g,
            "g_mod": 0,
            "system_sha256": computed_sha,
            "entry_sha256": entry_sha,
        }
    g_gcd = gcd(g_mod, modulus)
    if g_gcd != 1:
        return {
            "entry_id": entry["entry_id"],
            "mode": "odd_modular",
            "modulus": modulus,
            "modulus_is_prime": mod_prime,
            "verified": False,
            "reason": "non_unit_modular_rhs_dot_product",
            "g": g,
            "g_mod": g_mod,
            "gcd_g_modulus": g_gcd,
            "system_sha256": computed_sha,
            "entry_sha256": entry_sha,
        }
    return {
        "entry_id": entry["entry_id"],
        "mode": "odd_modular",
        "modulus": modulus,
        "modulus_is_prime": mod_prime,
        "verified": True,
        "g": g,
        "g_mod": g_mod,
        "gcd_g_modulus": g_gcd,
        "system_sha256": computed_sha,
        "entry_sha256": entry_sha,
    }


def verify_bundle(
    bundle: dict,
    *,
    expected_system_sha256s: dict[str, str] | None = None,
    max_pollard_steps: int = MAX_POLLARD_STEPS,
) -> dict:
    """Verify every entry in a ``hypersearch.linear-infeasibility-certificate/v1`` bundle."""
    fields(bundle, "schema entries")
    if bundle["schema"] != SCHEMA:
        raise ValueError("unsupported linear infeasibility certificate schema")
    entries = bundle["entries"]
    if type(entries) is not list or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError("certificate bundle requires 1 to 10000 entries")

    if expected_system_sha256s is not None and type(expected_system_sha256s) is not dict:
        raise ValueError("expected_system_sha256s must be a mapping of entry_id to sha256")

    seen_ids: set[str] = set()
    results: list[dict] = []
    union_primes: set[int] = set()
    unfactored: set[int] = set()
    failed: list[str] = []

    for entry in entries:
        if type(entry) is not dict or "entry_id" not in entry:
            raise ValueError("malformed certificate entry")
        eid = entry["entry_id"]
        text(eid)
        if eid in seen_ids:
            raise ValueError(f"duplicate certificate entry_id: {eid}")
        seen_ids.add(eid)
        exp_sha = expected_system_sha256s.get(eid) if expected_system_sha256s is not None else None
        res = verify_entry(entry, expected_system_sha256=exp_sha, max_pollard_steps=max_pollard_steps)
        results.append(res)
        if res["verified"]:
            for p in res.get("exceptional_primes", ()):
                union_primes.add(p)
            for u in res.get("unfactored_cofactors", ()):
                unfactored.add(u)
        else:
            failed.append(eid)

    if expected_system_sha256s is not None:
        missing_expected = sorted(set(expected_system_sha256s) - seen_ids)
        if missing_expected:
            raise ValueError(f"missing expected system entries: {missing_expected}")

    return {
        "schema": SCHEMA,
        "verifier": VERIFIER,
        "verified": not failed,
        "entry_count": len(results),
        "verified_count": len(results) - len(failed),
        "failed_entries": failed,
        "union_exceptional_primes": sorted(union_primes),
        "unfactored_cofactors": sorted(unfactored),
        "factorization_complete": not unfactored,
        "bundle_sha256": digest(encode(bundle)),
        "entries": results,
        "evidence_kind": "exact_linear_infeasibility_certificate_check",
        "formal_proof": False,
        "novelty_assessed": False,
    }


def check_certificate_file(
    path: Path | str,
    *,
    require_canonical: bool = True,
    expected_bundle_sha256: str | None = None,
    expected_system_sha256s: dict[str, str] | None = None,
    max_pollard_steps: int = MAX_POLLARD_STEPS,
) -> dict:
    """Read-only verification of a certificate JSON file with strict canonical check."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("certificate path must be a regular non-symlink file")
    size = p.stat().st_size
    if size == 0 or size > MAX_FILE_BYTES:
        raise ValueError("certificate file is empty or exceeds admitted byte bound")
    raw = p.read_bytes()
    parsed = parse(raw, maximum=MAX_FILE_BYTES)
    canonical = encode(parsed)
    if require_canonical and raw not in (canonical, canonical + b"\n"):
        raise ValueError("certificate file is not in canonical JSON encoding")
    receipt = verify_bundle(
        parsed,
        expected_system_sha256s=expected_system_sha256s,
        max_pollard_steps=max_pollard_steps,
    )
    if expected_bundle_sha256 is not None:
        sha(expected_bundle_sha256)
        if receipt["bundle_sha256"] != expected_bundle_sha256:
            raise ValueError("certificate bundle_sha256 mismatch")
    receipt["file_bytes"] = len(raw)
    receipt["file_sha256"] = digest(raw)
    return receipt
