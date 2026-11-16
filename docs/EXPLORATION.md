# Admitted exploration tasks — 0.10.0 development

Before a study is frozen, someone tries things: a quick count, a search for
a counterexample, a check that a protocol is feasible at all. Until 0.10.0
that happened outside the harness. Nothing recorded it, so a reviewer could
not tell what had been tried before a preregistration was written, and a
consumer whose rules forbid running research outside the harness had no
legal way to explore.

An exploration task runs **one committed program** on frozen arguments,
exactly as a [pinned-program task](PROGRAMS.md) does, and records what it
printed in a receipt. The receipt is a **log of what was tried, never
evidence**:

- the program prints `{"observations": {...}}` and nothing else; it cannot
  print a `holds` verdict, and output with any other field is
  `EXECUTION_FAILED`;
- every record carries `evidence_kind: "exploration_log"` and
  `citable: false`, together with `result_checked_by_instrument`,
  `formal_proof` and `novelty_assessed` all false; a receipt edited to say
  otherwise is refused by the validator;
- the study, census and program routes refuse exploration bundles and
  receipts (as a bundle, as a replay parent and in `trusted_receipt`);
- `check-export` has no exploration route, and an exploration receipt found
  in an export directory is reported as the problem
  `exploration receipt is not evidence`, so a family check that contains one
  is never `ok`.

Everything else is the program route: same source admission (printable
ASCII, at most 256 KiB, bound by SHA-256), same isolated interpreter and
limits, same Store, leases, attempt ceiling, stopping and
`abandon-attempt`, same receipts with replay. A replay of an exploration
compares observations by canonical encoding, so a non-deterministic probe
shows up as `replay_matches_parent: false`.

## What it is for, and what it is not

It turns "we ran something" into a record of which bytes ran, on what
input, with what output, so that a later preregistration can cite *that
an exploration happened* and what it saw, and a reviewer can judge whether
the frozen question was chosen after looking. It does not make the
observations true, and it does not replace a frozen study: a result that
matters is re-asked as a frozen census or program study (by its own rules,
for example two separately written programs) and only that receipt is
evidence.

It is not a sandbox. As for programs, the code runs with the operator's
file and network access; run only programs from a consumer commit you have
read.

## Commands

```sh
CACHE=$(mktemp -d)  # private and empty
PYTHONPATH=src python -B -S -P -X pycache_prefix="$CACHE" -m hypersearch run-exploration \
  --bundle /outside-source/bundle.json --consumer-root /pinned-consumer \
  --db /outside-source/explore.sqlite --export /outside-source/explorations
```

`replay-exploration` takes `--receipt`, `--expected-receipt-sha256` and
`--replay-id`. Exit 0 means `EXPLORATION_RECORDED`; 2 is everything else
(`EXECUTION_FAILED`, `INCOMPLETE`, a refused start, a replay mismatch).
There is no exit 1: an exploration never refutes anything.

Keep exploration databases and export directories apart from those of
frozen studies. The routes would refuse to mix them anyway, but a separate
directory keeps `check-export` reports about evidence free of logs.

## Schemas

All closed, with the strict JSON encoding of the study schemas.

- `hypersearch.exploration-manifest/v1`: schema, study_id, question,
  limits, artifact_sha256 (preregistration, claim_record and program).
- `hypersearch.exploration-bundle/v1`: schema, study_id, consumer,
  instrument, question, artifacts, limits. The verifier must be
  `hypersearch.exploration/v1`. Artifacts are exactly study_manifest,
  preregistration, claim_record and program. The `preregistration`
  artifact is the exploration's plan (what is probed and why); the
  `claim_record` is the consumer record the exploration serves, which may
  be a lane or open problem rather than a claim.
- Question: adapter (`exploration-program`), program_sha256, arguments,
  claim_type (`exploration-log`), assumptions_sha256 (the plan's digest).
- Limits: as for programs (`db_max_attempts`, `timeout_seconds` 1..21600,
  `commit_margin_seconds` 5..60, `memory_megabytes` 64..65536).
- `hypersearch.exploration-execution/v1` and
  `hypersearch.exploration-receipt/v1` have the fields of their program
  counterparts. Task keys use the prefix `exploration-`; replay IDs are
  namespaced `hypersearch.exploration-replay-id/v1`.

The recorded verification has: scope (`consumer_exploration_output`),
program_sha256, arguments, observations (an object, at most 64 KiB and
depth 16), evidence_kind (`exploration_log`), citable (false),
result_checked_by_instrument (false), formal_proof (false),
novelty_assessed (false).

## Relation to issue #24

Issue #24 proposes goal-free formal exploration with an
`ExplorationTrace/v1` that is explicitly non-citable. This route is the
narrow first slice of that boundary for consumer programs: it fixes the
evidence boundary (non-citable receipts that no evidence path accepts)
without a formal-proof checker, a director or open-ended generation.

## Status — 2026-11-16

Implemented with tests written first (they failed against 0.9.0): recorded
and replayed observations, refused verdict and malformed output, mutual
refusal with the program route, a forged citable receipt refused,
`check-export` refusal, and the actual command line with its launch
contract. The program route's runner gained one parameter (how its output
is read); its receipts, schemas and verifier are unchanged, so `check-export`
reads 0.9.0 receipts as before. Author checks only; independent review and
consumer adoption are separate gates. No research executed.
