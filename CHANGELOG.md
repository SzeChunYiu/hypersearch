# Changelog

No stable release has been commissioned. Entries describe development work, not production certification.

## Unreleased — 0.3.0 development

- Add frozen bundle/execution/receipt contracts and bounded supplied-certificate
  run/replay through the existing Store, without a second scheduler.
- Demo/study acquisition binds exact task ID; generic queue ordering remains.
- Extract pure admission without changing verifier semantics/IDs/bounds.
- Bind source/input pins, external receipt commitments and immutable export
  recovery. Invalid requests never grant work; failed attempts remain charged.
- Bind replay IDs atomically within the database; changed lineage cannot reuse
  an ID to obtain a fresh grant. Receipts bind the complete wrapper separately.
- Additive APIv1 development contract, not stable release or consumer adoption.
  New pins require conformance/rollback; historical instruments remain frozen.

## Development baseline — 0.2.0

Development upgrade from the original 0.1.0 foundation; no stable 0.1.0 release is implied.

- Durable local task store, bounded zero-sum search, independent subset recomputation and CLI.
- Exact managed-material inventory and development release/API manifest with CI consistency checks.
- Commit-pinned CI actions and administrative ownership routing.
- Consumer adoption contract and twin-system improvement protocol.
- Bounded exact multiwise Davenport certificate verification; not a frontier-scale solver.
- Validate bundled demo requests before persistent state or attempt acquisition.
  Existing failed records remain intact; no task schema or verifier change.
  Rollback is an explicit source-pin return, not database history deletion.

Breaking schema or evaluator changes require explicit migration notes and consumer revalidation before release.

## 0.5.0 development — shadow recommendation schemas

Adds a pure closed-JSON observation/policy recommendation API with explicit
no-authority output, three declared-score baselines and synthetic conformance.
No existing study/review schema or verifier changes. Exact pins remain required;
existing studies retain their original evaluator. This is an initial issue #16
software increment, not completion or director effectiveness evidence.

## 0.5.0 development — executed-code admission correction

- Study and review commands require the launch
  `-B -S -P -X pycache_prefix=<new empty directory>`, an empty cache prefix, no
  inspect mode, and an import path made only of the pinned `src` and the
  interpreter's standard library. Previously an ignored cache, or an ignored
  standard-library-named file in the launch directory, executed while source
  hashes passed, and a false witness could be committed and exported as
  VERIFIED_WITNESS.
- Admission refuses any entry named `__pycache__` under the pinned `src` tree
  and any redirected-cache entry for a pinned module.
- Unexpected failures inside a command exit 2; exit 1 stays a completed
  refutation. Interpreter-level failures still exit 1 with nothing on stdout, so
  consumers should require the printed `outcome_status` as well.
- These checks catch honest launch mistakes. They do not defend a
  non-conforming launch against hostile files, which can run before them.
- **Consumer migration:** add `-P` to launches of these commands; do not use
  the installed console script for them. A core checkout holding caches,
  including ones written by running the tests or demo without `-B`, is refused
  until they are deleted. In-process callers own their own boundary.
- No schema, verifier, API or version change; the exact commit identifies the
  instrument. Adoption is a consumer pin PR with that consumer's own controls.

## 0.6.0 development — exhaustive census tasks

- New verifier `hypersearch.zero-sum-census/v1` and four closed
  `hypersearch.census-*/v1` schemas: an exhaustive count of sequences of a
  given length over a small group with no zero-sum of length at most m and,
  optionally, none of length at least q. Commands `run-census` and
  `replay-census`.
- The census uses the existing Store, lease, receipt, export and replay path.
  To share it, the study executor takes a route; the supplied-witness route's
  behaviour, schemas, verifier IDs and bounds are unchanged.
- A reported example is rechecked by the parent with separate code, once per
  process. The parent applies necessary conditions to the level profile and
  refuses a zero that contradicts the standard zero-sum-free sequence. Any
  other zero has no independent check and needs a known-answer control and
  review. The census commit margin is 5 to 60 seconds.
- Additive development contract. The version changes, so every frozen bundle
  must name 0.6.0 with this commit; existing studies keep their old pins.

## 0.7.0 development — pinned-program tasks

- New verifier ID `hypersearch.pinned-program/v1` and four closed
  `hypersearch.program-*/v1` schemas. Commands `run-program` and
  `replay-program` run one consumer-committed, hash-bound Python program in an
  isolated interpreter and record its `{"holds", "summary"}` output.
- The instrument binds the program, its arguments and its limits, admits
  only source text, kills the program's process group, and requires a replay
  to reproduce the output. **It does not check the program's logic**; receipts say
  `result_checked_by_instrument: false`.
- Uses the existing Store, lease, receipt, export and replay path. The
  supplied-witness and census routes are unchanged.
- Additive development contract. The version changes, so every frozen bundle
  must name 0.7.0 with this commit; existing studies keep their old pins.
- Replay comparison for every frozen route is now by canonical encoding, so
  outcomes that differ only as `1` versus `true` no longer match. Typed
  study and census outcomes are unaffected.

## 0.7.1 development — a refused start says why

- A frozen task that cannot be leased now reports which refusal occurred:
  `attempt budget exhausted` or `task is leased to another attempt`, with the
  database's `budget` and the `task_state`. Before, both read "task
  unavailable or attempts exhausted". Found in use: a family of ten studies
  frozen with a ceiling of eight would have had its last two studies refused
  with no indication that the ceiling, not the task, was the cause.
- Documentation states that `db_max_attempts` counts every lease in one
  database, across tasks.
- No schema, verifier or receipt changes. The version changes, so a bundle
  that wants this behaviour must name 0.7.1 with this commit; existing
  studies keep their old pins.
