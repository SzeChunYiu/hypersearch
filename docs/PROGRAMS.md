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

- The program is one Python **source text** file, at most 256 KiB, named in
  the bundle as the artifact `program` and bound by SHA-256 to the committed
  file. It must be printable ASCII with tabs and newlines only. An archive or
  compiled file under a `.py` name, a carriage return, and any non-ASCII
  character (including invisible or direction-changing ones) are refused, so
  what a reviewer reads is what runs.
- The instrument writes those bundled bytes into a new empty directory and
  runs `python -B -I -S -c <bootstrap> program.py`. The bootstrap is one
  expression that compiles the file as source and executes it as the
  `__main__` module, so an encoding declaration has no effect. `__file__` is
  not defined. There are no site packages, none of the caller's environment
  (a default `PATH`; the interpreter may add its own locale variable), no
  bytecode, and that directory is the working directory. Only the standard
  library is importable.
- The program reads its `arguments` (a frozen JSON object of at most 4 KiB
  and depth at most 16, counting the object itself and the innermost value)
  from standard input.
- It must exit 0 and print exactly one JSON object
  `{"holds": true|false, "summary": {...}}`: at most 64 KiB of standard
  output including whitespace, at most 64 KiB when re-encoded in ASCII,
  depth at most 16 counted the same way, with integers (at most 4,300
  digits), strings,
  lists, objects, booleans and null only. `holds` is the program's own
  answer to the preregistered question; `summary` carries the counts the
  preregistration asks for.
- Limits: `timeout_seconds` (1..21600), `memory_megabytes` (64..65536, an
  address-space limit), `commit_margin_seconds` (5..60), `db_max_attempts`.
  The last is a ceiling on **all leases granted in one database**, not per
  task: a family sharing a database needs at least one attempt per study plus
  one per replay run there, every bundle using it must name the same ceiling,
  and a second database counts separately.
  A written file is capped at 1 MiB; the number of files is not capped.
- When the program ends or times out, **its process group is killed**. A
  process the program deliberately moves out of that group survives.

This is isolation from accidental inputs, **not a security sandbox**. The
program runs with the operator's file and network access. Run only programs
from a consumer commit you have reviewed.

## Outcomes

A start that is refused before any lease exits 2 and prints
`"execution": "not_started"` with no `outcome_status` and a `reason`:
`attempt budget exhausted` when the database's ceiling is spent, `task is
leased to another attempt` when the ceiling has room but the task is held, or
`task was completed by another attempt` when it finished while this start was
being admitted (run the command again for its receipt as `not_rerun`). It also
prints the `budget` (`maximum`, `spent`) and the stored `task_state`, read
after the refusal. When the ceiling is spent and the task is also held, the
ceiling is named. `running` includes a lease whose holder died; it is
reclaimed after expiry if the ceiling has room. A refused start charges
nothing and writes no receipt, but the task (for a replay, its replay ID)
stays registered as pending in that database. The supplied-witness and census
routes print the same object; the reason, budget and state are new in 0.7.1.

`PROGRAM_HOLDS` (exit 0), `PROGRAM_FAILS` (exit 1), `EXECUTION_FAILED` or
`INCOMPLETE` (exit 2). A non-zero program exit, a death by signal, or
malformed, oversized or too deeply nested output is `EXECUTION_FAILED`; a
timeout is `INCOMPLETE`. Neither carries a result, and as for studies either
completes its task: another attempt is a replay or a new bundle. Hitting the
memory or file limit normally ends the program and so is `EXECUTION_FAILED`,
but a program that handles the error itself can still finish. Diagnostics of
a failed run can contain host-specific paths; they are not part of the
compared outcome.

A replay must reproduce the recorded outcome exactly, compared by its
canonical encoding (so `1` and `true` differ). A program must therefore be
deterministic: no clocks, random seeds, hash-order dependence or host
details in its output. A differing replay exits 2 with
`replay_matches_parent: false`.

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
request. Tests use trivial synthetic programs and cover recording, replay and
replay mismatch, isolation, malformed and too deeply nested output, a
non-zero exit after valid output, memory and file limits observed from
inside the program, a timeout with a child in the same process group,
admission with a re-frozen manifest for each refused question and limit
field and for each manifest binding, archives, bytecode and non-ASCII source
under a `.py` name, an encoding declaration, execution in the real main
module, cross-route refusal and the real command line.

Review by a separate session started by the author (declared separation, not
authenticated independence) found four blocking defects in the first
version, all fixed: a replay differing only as `1` versus `true` was reported
as matching; deeply nested output crashed the parent after the run and left
the task open; an archive or bytecode named `.py` ran; and the documentation
claimed every started process is killed. A confirmation pass found those
fixed and two further points, also fixed: invisible Unicode characters were
admitted in source, and the launch wrapper ran the program outside the real
main module. Identity binding, cross-route refusal, the output parser and
the other routes held throughout. The last fixes were checked by the author
and CI, not reviewed again.

The 0.7.1 refusal reasons have author checks and one review by a separate
session started by the author, which found a third refusal case (a task
completed by another attempt during admission) reported under the wrong
reason and three mutations the first test did not catch; both are fixed. Not
independent certification.

Limits. Not a sandbox; a process that leaves the group survives. The
instrument never checks program logic. Determinism
across interpreter versions is the program author's responsibility and is
only detected, not ensured, by replay. POSIX only. Independent review, public
CI and consumer adoption are separate gates. No research executed, no claim
promoted.
