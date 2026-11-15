# Frozen exhaustive-census tasks — 0.6.0 development

A census answers one finite question exhaustively: over a small finite abelian
group, **how many multisets of n elements (sequences up to order) have no
nonempty zero-sum subsequence of length at most m and, optionally, none of
length at least q?** A count of zero is an upper-bound statement about every
sequence of that length; a positive count comes with one example.

It does not prove a theorem, assess novelty, accept a claim or lift any
consumer hold. It is one implementation of a finite computation.

## What the verifier does

`hypersearch.zero-sum-census/v1` walks every multiset once, as a nondecreasing
sequence of element codes, and cuts a branch exactly when the new term closes
a zero-sum of length at most m. That property is inherited by subsequences, so
every qualifying multiset of size d + 1 extends one of size d and the walk is
complete. The long condition is not inherited and is tested only on complete
sequences, as a deletion of at most n − q terms summing to the total.

Bounds: group order at most 64, rank at most 3, length at most 20,
1 ≤ m ≤ n, and q either null or m < q ≤ n with n − q ≤ m − 1. Anything else is
refused before enumeration. The bounds limit the question, not the work: a
question inside them can need far more time than any admitted timeout, and
then ends `INCOMPLETE`.

The result has `count`, an `example` (the verifier reports its first survivor
in walk order, or null), and `levels`: for each size d ≤ n, the number of multisets of that size
with no zero-sum of length at most m. The profile is deterministic, so a
replay must reproduce it exactly.

Examples a census can express: "no zero-sum-free sequence of length D(G)"
(m = n), "every sequence of length η(G) has a zero-sum of length at most
exp(G)" (m = exp(G)), or a structural lemma about sequences with neither short
nor long zero-sums.

## Running one

The route is the frozen-study route with a different question and verifier:
same Store, exact-task grant, lease, fenced completion, receipt export and
digest-bound replay, and the same required launch and source checks. Read
[frozen studies](STUDIES.md) first; everything there about launch, effect
admission, recovery and replay applies unchanged.

```sh
CACHE=$(mktemp -d)  # private and empty
PYTHONPATH=src python -B -S -P -X pycache_prefix="$CACHE" -m hypersearch run-census \
  --bundle /outside-source/bundle.json --consumer-root /pinned-consumer \
  --db /outside-source/tasks.sqlite --export /outside-source/receipts
```

`replay-census` takes `--receipt`, `--expected-receipt-sha256` and
`--replay-id` exactly as `replay-study` does.

Exits: 0 `CENSUS_EMPTY` (count is zero); 1 `CENSUS_NONEMPTY`; 2 refusal,
unavailable grant, incomplete or failed execution, or replay mismatch. Require
the printed `outcome_status`, not the exit code alone.

## Schemas

All closed, with the strict JSON encoding of the study schemas.

- `hypersearch.census-manifest/v1`: schema, study_id, question, limits,
  artifact_sha256 (preregistration and claim_record).
- `hypersearch.census-bundle/v1`: schema, study_id, consumer, instrument,
  question, artifacts, limits. Consumer and instrument are as in the study
  bundle; the verifier must be the census verifier. Artifacts are exactly
  study_manifest, preregistration and claim_record. There is no certificate:
  nothing is supplied except the question.
- Question: adapter (`zero-sum-census`), moduli, length, short_max, long_min,
  claim_type (`exhaustive-census`), assumptions_sha256.
- Limits: db_max_attempts, timeout_seconds (1..3600), commit_margin_seconds
  (5..60; the parent's recheck of a 20-term example takes about a second and
  runs inside the lease).
  `db_max_attempts` counts every lease in the database, across tasks; a
  refused start says whether the ceiling is spent or the task is held
  (`reason`, `budget`, `task_state`).
- `hypersearch.census-execution/v1` and `hypersearch.census-receipt/v1` have
  the fields of their study counterparts. Task keys use the prefix `census-`.
  A study bundle is refused by the census route and the reverse.

Outcome status is `CENSUS_EMPTY`, `CENSUS_NONEMPTY`, `EXECUTION_FAILED` or
`INCOMPLETE`. Timeouts and crashes carry no result and are never a count.
As for studies, an `INCOMPLETE` or `EXECUTION_FAILED` receipt completes its
task: the same bundle is then `not_rerun`, and another attempt is a replay or
a new bundle.

## What is and is not checked

- The parent validates the child's result against the frozen question and
  applies necessary conditions to the level profile: it starts 1, |G| − 1;
  each level is at most (|G| − 1) times the one before and at most the number
  of multisets of that size; an empty level is followed only by empty levels.
- The parent refuses a zero that contradicts the standard zero-sum-free
  sequence (each basis element e_i repeated n_i − 1 times): no level up to
  that length may be empty, and the count is positive when n is at most that
  length. This catches only zeros below Σ(n_i − 1).
- A reported example is rechecked by the parent with a separate subset
  enumeration and must be in walk order. A false "nonempty" therefore needs
  two agreeing errors. The parent does not check that it is the first
  survivor.
- **A count of zero above that length has no independent check.** It rests on
  the single enumeration and on replay determinism. Before a zero is relied on, run a
  matching known-answer control (a neighbouring length with a known positive
  count, or a group with a published value) and have the code reviewed.
- Tests compare the verifier with a brute-force oracle on small groups and
  with known constants of C_3^2, C_2^3, C_4^2 and C_5.

Consumer adoption is a separate pin PR with that consumer's own conformance,
refusal and rollback evidence. Existing studies keep their pins.

## Status — 2026-11-15

Motivation: the supplied-witness route takes one certificate per task and
cannot express an upper bound or an exhaustive family. A consumer needed
statements of the form "no sequence of length n avoids zero-sums of these
lengths".

Implemented: one census verifier and a census route that reuses the study
executor through a route parameter, so the Store, lease, fenced completion,
receipt export and replay logic exists once. The study executor's refactor is
covered by the unchanged existing tests.

Author checks on Python 3.11, 3.12 and 3.13: counts in the pull request. The
verifier agrees with a brute-force oracle on thirteen small cases and
reproduces D(C_3^2) = 5, eta(C_3^2) = 7, eta(C_2^3) = 8, D(C_4^2) = 7 and
D(C_5) = 5. A census of order-27 scale (C_3 x C_9, length 12) walked about
25 million nodes in 30 seconds. Only synthetic fixtures and these small groups
were run; no consumer research question was computed here.

Review by a separate session started by the author (declared separation, not
authenticated independence): 13,089 comparisons of count, profile and example
against two other algorithms, no mismatch; four non-blocking findings, all
addressed (parent profile and standard-sequence checks, one cached example
recheck with a 5-second minimum margin, boundary tests, documentation).

Limits. One implementation. A count of zero above the standard sequence's
length is not independently checked. No formal proof. Public CI and consumer
adoption are separate gates. No research executed, no claim promoted.
