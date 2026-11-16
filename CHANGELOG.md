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
  `attempt budget exhausted`, `task is leased to another attempt` or `task
  was completed by another attempt`, with the database's `budget` and the
  `task_state`. Before, all read "task unavailable or attempts exhausted".
  Found in use: a family of studies frozen with a ceiling below their number
  would have had its last studies refused with no indication that the
  ceiling, not the task, was the cause.
- Documentation states that `db_max_attempts` counts every lease in one
  database, across tasks.
- No schema, verifier or receipt changes. The version changes, so every
  frozen bundle must name 0.7.1 with this commit; existing studies keep their
  old pins.
- The demo command and the review workflow still report an unavailable task
  without saying why; left for a later change.

## 0.8.0 development — export check and resource usage

- New read-only command `check-export --route {study,census,program} --export
  DIR [--export DIR ...] [--expected FILE]`. It re-verifies exported receipts
  with the routes' existing validators: each file name against the digest of
  its bytes, the committed encoding, exactly one original per study, and each
  replay against a present original of the identical bundle with the
  comparison recomputed. It opens no database and runs no verifier or
  program. Exit 0 when everything holds, 1 on any problem, 2 on a refused
  command line, launch or expected file.
- New closed schema `hypersearch.expected-outcomes/v1`: a consumer's list of
  studies with the outcome status, optionally the digest of the registered
  part of a program's summary, and whether a matching replay is required.
- `run-*` and `replay-*` print `usage` for a completed execution:
  `wall_milliseconds`, `cpu_milliseconds` and `max_rss_kilobytes` of the
  route's child process. Programs are now reaped with `wait4`, so the figures
  are the program's own. **Usage is not in the receipt**: no receipt field,
  schema, verifier or exit code changes, and `not_rerun` and `not_started`
  carry no usage. Consumers that compare the printed object against an exact
  set of keys must admit the new key.
- Found in use: receipts recorded elapsed wall time only, so a slow program
  could not be told from a busy host, and the mechanical re-check of a
  family's receipts was done by hand.
- A process that ignores SIGCHLD loses its children's exit statuses, and the
  setting is inherited across `exec`. The `run-*`, `replay-*`, review and
  `check-export` commands now restore the default before anything runs, so a
  launcher that ignores SIGCHLD no longer changes an outcome; before, a
  program's output was read as if it had exited 0. A library caller in such
  a process gets `EXECUTION_FAILED` for a program whose status was lost, never
  a reading of exit 0, and a timeout stays `INCOMPLETE`.
- Additive development contract. The version changes, so every frozen bundle
  must name 0.8.0 with this commit; existing studies keep their old pins.
  `check-export` also reads receipts of 0.7.0 and 0.7.1, whose receipt
  validators are unchanged apart from the version; run and replay still
  refuse them. Every release reviews that set (`EARLIER`).
- Planned, not in this change: an admitted exploration route, a CPU-time
  limit and a family manifest; see the roadmap.

## 0.9.0 development — a stopped launch releases its task

- Found in use: a launch stopped by its operator kept its task leased for
  the timeout plus the margin (hours), so every relaunch was refused as
  `task is leased to another attempt`; and SIGTERM to the launcher skipped
  the clean-up that kills the program's process group, so the program could
  outlive it.
- `run-*` and `replay-*` handle SIGTERM, SIGINT and SIGHUP while the lease
  is held and the outcome undecided: the child is killed (a program's whole
  group), the task returns to `pending` with an `interrupted` event, the
  command prints `"execution": "interrupted"` and exits 2. The attempt stays
  charged and the fence spent, so the stopped attempt can never complete and
  a relaunch is accepted at once. Elsewhere a stop waits for the step in
  progress (a commit is never cut) and is then delivered as before; ignored
  signals stay ignored. In-process callers get `Interrupted`, a
  `BaseException`.
- On Linux every route's child is started with the parent-death signal
  (`PR_SET_PDEATHSIG`, SIGKILL), so a SIGKILLed launcher takes its child
  with it. The child's own descendants are not covered.
- New command `abandon-attempt --db --task --fence --reason`. Leases taken by
  the frozen routes record their holder (process id, start time, boot id,
  process-id namespace, host). The command frees a lease only when that holder is dead, appends an
  `abandoned` event, keeps the attempt charged, and never deletes results,
  events, receipts or exports. It refuses a live, unrecorded or uncheckable
  holder, a stale fence and a pending or completed task. A holder in another
  process-id namespace, or one whose `/proc` entry is hidden (`hidepid`) but
  which the kernel still has, is unknown and refused, as is any check made
  through a `/proc` mounted from another process-id namespace; with an empty host
  name nothing is recorded and launches run as before.
- Independent review fixes: a stop that lands after the program is reaped
  but before its return code is set is a stop, not an `EXECUTION_FAILED`
  receipt; the namespace and hidden-`/proc` cases above were read as dead.
- Store: new table `event_details`; the earlier tables keep their
  definitions, so 0.8.0 opens a 0.9.0 database and grants a released task.
  `status` prints each event's `detail`. New `Store.existing`,
  `Store.interrupt`, `Store.abandon` and the `holder` argument.
- No receipt, schema or verifier change. The version changes, so every
  frozen bundle must name 0.9.0 with this commit; existing studies keep their
  old pins. `check-export` also reads receipts of 0.8.0, whose receipt
  validators are unchanged apart from the version (`EARLIER`).
- Not in this change: heartbeat leases, time budgets and a read-only status
  with holder liveness.
