# Frozen pinned-program tasks — 0.7.0 development

A pinned-program task runs **one program that the consumer has committed**,
under the same frozen route as studies and censuses, and records its small
JSON output in a receipt. It exists so that a finite computation which no
built-in verifier covers can still be frozen before it runs, charged to a
budget, receipted and replayed.

**The instrument does not check that the program is correct.** It checks which
program ran, on what input, under what limits, and that a replay produced the
same output. Every receipt says `result_checked_by_instrument: false`. Whether
the program proves anything is for the consumer's review to establish, for
example by requiring two independently written programs to agree.

## What runs

- The program is one Python source file, at most 256 KiB, named in the bundle
  as the artifact `program` and bound by SHA-256 to the committed file.
- The instrument writes those bundled bytes into a new empty directory and
  runs them with `python -B -I -S`: no site packages, no ambient environment
  (only a default `PATH`), no bytecode, and that directory as the working
  directory. Only the standard library is importable.
- The program reads its `arguments` (a JSON object of at most 4 KiB, frozen in
  the question) from standard input.
- It must exit 0 and print exactly one JSON object
  `{"holds": true|false, "summary": {...}}` of at most 64 KiB, with integers,
  strings, lists, objects, booleans and null only. `holds` is the program's
  own answer to the preregistered question; `summary` carries the counts the
  preregistration asks for.
- Limits: `timeout_seconds` (1..21600), `memory_megabytes` (64..65536, an
  address-space limit), `commit_margin_seconds` (5..60), `db_max_attempts`.
  Files the program writes are capped at 1 MiB each. On timeout the program
  and every process it started are killed.

This is isolation from accidental inputs, **not a security sandbox**. The
program runs with the operator's file and network access. Run only programs
from a consumer commit you have reviewed.

## Outcomes

`PROGRAM_HOLDS` (exit 0), `PROGRAM_FAILS` (exit 1), `EXECUTION_FAILED` or
`INCOMPLETE` (exit 2). A non-zero program exit, malformed or oversized output,
a memory or file limit, or a crash is `EXECUTION_FAILED`; a timeout is
`INCOMPLETE`. Neither carries a result, and as for studies either completes
its task: another attempt is a replay or a new bundle.

A replay must reproduce `holds` and `summary` exactly, so a program must be
deterministic: no clocks, random seeds, hash-order dependence or host details
in its output.

## Running one

Launch, source checks, effect admission, recovery and replay are those of
[frozen studies](STUDIES.md).

```sh
CACHE=$(mktemp -d)  # private and empty
PYTHONPATH=src python -B -S -P -X pycache_prefix="$CACHE" -m hypersearch run-program \
  --bundle /outside-source/bundle.json --consumer-root /pinned-consumer \
  --db /outside-source/tasks.sqlite --export /outside-source/receipts
```

`replay-program` takes `--receipt`, `--expected-receipt-sha256` and
`--replay-id`.

## Schemas

All closed, with the strict JSON encoding of the study schemas.

- `hypersearch.program-manifest/v1`: schema, study_id, question, limits,
  artifact_sha256 (preregistration, claim_record and program).
- `hypersearch.program-bundle/v1`: schema, study_id, consumer, instrument,
  question, artifacts, limits. The verifier must be
  `hypersearch.pinned-program/v1`. Artifacts are exactly study_manifest,
  preregistration, claim_record and program.
- Question: adapter (`pinned-program`), program_sha256, arguments, claim_type
  (`program-output`), assumptions_sha256.
- `hypersearch.program-execution/v1` and `hypersearch.program-receipt/v1` have
  the fields of their study counterparts. Task keys use the prefix
  `program-`. Bundles of other routes are refused and the reverse.

The recorded verification has: scope (`consumer_program_output`),
program_sha256, arguments, holds, summary, evidence_kind
(`pinned_program_output`), result_checked_by_instrument (false), formal_proof
(false), novelty_assessed (false).

## What this is worth

Less than a built-in verifier and more than an unrecorded run. It fixes the
question, the code and the limits before execution, makes the answer
reproducible, and prevents a quiet re-run after an unwelcome result. It adds
no assurance about the program's logic. Consumer adoption is a separate pin PR
with that consumer's own conformance, refusal and rollback evidence.

## Status — 2026-11-15

Motivation: every new kind of finite computation needed its own built-in
verifier, its own review and its own consumer pin before one task could run.
A consumer with many heterogeneous exhaustive checks could not freeze and
receipt them at all.

Implemented: the program route, reusing the study executor through its route
parameter. Author checks on Python 3.11, 3.12 and 3.13 are in the pull
request. Tests use trivial synthetic programs and cover recording, replay,
isolation, every malformed output, memory and file limits, timeout with a
surviving grandchild, closed admission, cross-route refusal and the real
command line.

Limits. Not a sandbox. The instrument never checks program logic. Determinism
across interpreter versions is the program author's responsibility and is
only detected, not ensured, by replay. POSIX only. Independent review, public
CI and consumer adoption are separate gates. No research executed, no claim
promoted.
