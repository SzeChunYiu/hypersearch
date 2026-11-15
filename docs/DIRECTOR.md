# Pure shadow recommendation API

See [design](DIRECTOR_DESIGN.md) for options, scope and public provenance.
This interface is software-only. Declared gain is not scientific acceptance.

Use hypersearch.director.recommend(observation_bytes, policy_bytes,
expected_observation_sha256=..., expected_policy_sha256=...).
Inputs must be immutable UTF-8 JSON bytes. SHA256 covers exact bytes; changed
whitespace changes identity. Outputs are sorted-key compact ASCII-escaped JSON
bytes, not a durable execution receipt, and contain no self digest.

Observation fields:
- schema: hypersearch.director-observation/v1
- observation_id: nonempty text, at most 256 characters
- consumer_commit: 40 lowercase hexadecimal characters
- gain_unit, cost_unit: nonempty text, shared across candidates
- gate: permission, hold, dependency
- candidates: at most 1000 candidate objects

Candidate fields:
- candidate_id: unique nonempty text, at most 256 characters
- task_sha256: 64 lowercase hexadecimal characters
- declared_gain: integer in [-10^12, 10^12]
- declared_cost: execution, verification, coordination, recovery; each integer
  in [0, 10^12], total strictly positive
- gate: same closed object as observation

Gate vocabulary: permission allowed/pending/denied/revoked; hold clear/active;
dependency ready/pending/revoked. Gates are untrusted snapshot declarations,
not authenticated admission. No freshness is inferred.

Policy fields: schema hypersearch.director-policy/v1, policy_id and seed.
IDs: supplied-order/v1, declared-gain-cost/v1, seeded-hash-order/v1.
Seed is integer [0, 2^64-1], zero except for seeded hash order.
Ratio ties use candidate ID. Seeded order sorts SHA256 of canonical
{seed, candidate_id}, then ID; not a uniform-randomness claim.
Supplied order deliberately preserves input order. All policies use the same
positive-gain eligibility filter; no scores bypass permission or HOLD.

Schemas are closed. Booleans, floats, nonfinite values, duplicate keys, unknown
policies and invalid costs refuse. Input bytes are bounded at 1 MiB each.
Gain <= 0 is valid but excluded. Denied, pending and revoked remain distinct
reasons. Defer never clears a HOLD; stop never closes a scientific question.

Outputs bind input/policy digests, selected task digest, ranking and exclusions.
Every output states shadow mode, no authority, no execution and mandatory live
admission recheck. Pin the implementation independently. The caller retains the
recommendation. No CLI, filesystem export, Store, provider, grant or scheduler
integration is supplied.
