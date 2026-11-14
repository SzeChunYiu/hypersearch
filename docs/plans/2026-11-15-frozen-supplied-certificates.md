# Frozen supplied-certificate execution — historical design

This record began as the pre-implementation design. The bounded route was then
implemented and qualified at `18310cdef2167885cdb3c6ea5d73b1b1cc84f5c9`:
61 tests and governance passed, followed by nine independently executed hostile
controls. See [current qualification/status](../STATUS.md),
[operation](../STUDIES.md) and [implemented schemas](../STUDY_CONTRACT.md).
The alternatives and proposed interfaces below preserve the original decisions;
current consumer interfaces belong to their owning repositories. This design
record does not authorize research admission or mathematical promotion.
Scope: bounded ordinary-D and multiwise supplied certificates, never frontier search,
upper bounds, equality, novelty, manuscript acceptance or formal proof.

## Decision and alternatives

**Choose a synchronous Hypersearch study runner using its existing Store.** The
consumer binds its own committed study/claim/preregistration records and invokes
only the exact pinned core. The core admits, accounts for, verifies and records
the task. There is one queue/attempt authority and no new scheduler.

Alternatives considered:
- Consumer wraps existing `verify` commands and writes receipts: smallest patch,
  but duplicates execution bookkeeping and makes a private wrapper the effective
  research harness. Reject as the durable route.
- General plugin/workflow service: broad flexibility, but adds untrusted code,
  authentication and scheduling before bounded conformance works. Defer.
- Chosen runner: modest public schema/CLI work plus exact-task Store acquisition;
  preserves existing authority and supports deterministic certificate replay.

## Proposed interfaces

Public core:
```text
hypersearch run-study --bundle admitted-bundle.json --consumer-root DIR --db local.sqlite --export DIR
hypersearch replay-study --receipt prior.json --expected-receipt-sha256 DIGEST --replay-id ID --consumer-root DIR --db local.sqlite --export DIR
```
Consumer entry point:
```text
python scripts/hypersearch.py run-study --study PATH --consumer-commit SHA --core DIR --db PATH --export DIR
python scripts/hypersearch.py replay-study --receipt PATH --core DIR --db PATH --export DIR
```
Add `Store.acquire(worker, lease_seconds=60, *, task_id=None)`; a supplied ID is
an SQL-bound exact filter. Unknown/completed/unavailable tasks acquire nothing,
spend nothing and cannot accidentally execute earlier pending work. Existing
callers retain queue ordering. No arbitrary callbacks, import names or commands.

## Closed bundle and identity contract

Propose `hypersearch.study-bundle/v1`, with these exact top-level fields:
`schema`, `study_id`, `consumer`, `instrument`, `question`, `artifacts`, `limits`.
- `consumer`: repository identifier, 40-hex committed source SHA, claim ID,
  claim-record SHA256, preregistration SHA256, consumer-entrypoint SHA256.
- `instrument`: repository, 40-hex core commit, release version, API ID,
  one allowed verifier ID, SHA256 of each executed bundled source file.
- `question`: adapter ID (`ordinary-witness` or `multiwise-witness`), group
  moduli, integer k (exactly 1 for ordinary), supplied sequence length L,
  `claim_type=lower-bound-witness`, assumptions reference, intended bound L+1.
- `artifacts`: exactly `study_manifest`, `preregistration`, `claim_record`,
  `certificate`; each has repo-relative path, byte count, raw-byte SHA256 and
  base64 bytes. Input bytes become part of frozen task state, avoiding later reads.
- `limits`: DB-global attempt ceiling and verifier timeout, plus admitted byte/term bounds.
  Resource settings are explicit, versioned and cannot exceed supported policy.

The consumer constructs the transport bundle from files at externally specified
commit C; source `study.json` does not embed its own containing commit, avoiding
self-reference. C already contains the frozen preregistration and exact supplied
certificate digest. Consumer verifies object and working bytes, clean HEAD=C,
claim ID/version linkage and registry/archive gates before invoking core.

Admission rejects extra/missing fields, duplicate JSON keys, nonfinite values,
bool-as-int, malformed hashes, inconsistent lengths/groups/k, unsupported scope,
out-of-policy resources, symlink/traversal paths and wrong pin/source identities.
Core recomputes artifact hashes, strictly parses certificate bytes and enforces
the bundled verifier's closed schema/bounds before Store construction or grant.
Question/limits are extracted from the hashed study manifest, not separately
caller-selected overrides; the manifest binds the other three artifact digests.
The source-file set is fixed by the adapter release, not supplied by the candidate;
core compares actual runtime source hashes and checkout identity with the bundle.
Extract pure adapter validation for admission; revalidate after acquisition.
No verifier execution occurs during admission. Consumer-specific claim meaning
stays consumer-owned; core records these references without certifying them.

## Execution, receipts and restart

The full closed wrapper (`schema`, `kind`, `bundle`, `parent_receipt_sha256`,
`replay_id`) always has an immutable SHA256 spec identity, bound in the receipt.
Original task keys use that identity. Replay task keys instead hash the versioned
DB-scoped replay-ID namespace. Store.submit atomically binds that key to one full
wrapper: same ID/same wrapper is idempotent; changed parent/bundle conflicts.
Original runs require null parent/replay ID; replay requires trusted parent digest
and nonempty unique replay ID.
Use existing sorted-key compact JSON only for the closed envelope; explicitly
name this encoding and do not claim RFC8785/JCS compliance. Raw artifact hashes
always identify original bytes. CLI dispatch is a fixed map to trusted bundled
ordinary/multiwise verifier functions with frozen expected group and k.

An exact task lease runs verification under a bounded subprocess and the current
isolated-import discipline. Store.complete atomically records the complete
`hypersearch.study-receipt/v1` result with task/spec/input/instrument identities,
lease generation, runtime provenance, elapsed resources, outcome and diagnostics.
The receipt embeds the complete frozen execution wrapper, not just its digest.
Lease duration = admitted verifier timeout + explicit positive bounded commit
margin; expired/stale completion never exports a success receipt.
Outcomes are `VERIFIED_WITNESS`, `REFUTED_WITNESS`, `EXECUTION_FAILED`, or
`INCOMPLETE`; only the first carries L+1, always scoped to this supplied witness.
Only a completed schema-checked verifier rejection is REFUTED_WITNESS. Timeout,
malformed child output, exceptions or stale completion are never mathematical
negatives or bounds. Malformed admission is REFUSED before task creation.
Admitted failures/timeouts remain charged. A lost result leaves a charged lease;
normal expiry/fencing and the frozen DB-global attempt ceiling governs any reacquisition.

DB/export paths must lie outside both pinned source roots and not overlap each
other or input files. The immutable result row is the receipt authority. Export is a recoverable view:
write/fsync a temporary file, install under receipt-digest name without replacing
an existing path, and fsync its directory. Equal existing bytes are idempotent;
different/partial bytes are a distinct integrity error, never silently overwritten.
Crash after completion but before export re-exports the same committed result.
Repeated run-study returns the existing receipt and explicitly says not rerun.

Replay creates a separately charged task with original frozen bundle plus
`parent_receipt_sha256` and unique `replay_id`; it never mutates the old task.
Replay requires `--expected-receipt-sha256` from an external immutable commitment,
not a self-reported digest inside supplied JSON. Cooperative local Store lookup
may supply the commitment; this is not signatures or remote attestation.
Only that original instrument qualifies as exact replay. A new evaluator requires
an explicit study revision/pin transition. Compare deterministic outcome payloads;
timestamps, attempt IDs and timings belong outside that payload. Replay receipts
record contributor lineage; another agent is not an external mathematical referee.

## Acceptance plan before real studies

1. Pure admission positives: ordinary known-answer and multiwise C2 examples.
   Malformed/duplicate-key/bool/oversize/wrong group/k/digest/pin/scope requests
   must create no fresh database or change existing tasks/events/results/attempts.
2. Known valid and false witnesses: retain duplicate values as distinct positions;
   wrong task and fabricated packing fail; no upper/equality claim can be emitted.
3. Exact-task selection: unrelated earlier work is untouched; simultaneous grant,
   stale completion, lost reply, expiry and attempt exhaustion retain invariants.
4. Replay: same frozen bytes yield identical deterministic outcome; modified input,
   verifier, source, original receipt or pre-registration is refused, not retargeted.
5. Persistence: interruption before completion, after completion/before export,
   duplicate export and export collision preserve historical evidence and charges.
6. Consumer conformance: full registry/archive checks, clean and concealed-dirty
   source checks, known-answer receipts, independent second-host replay, new-pin
   transition and rollback on identical frozen fixtures. Existing studies stay pinned.

## Remaining gates and explicit non-goals

The design-stage implementation gate has been satisfied by the development
0.3.0 source, schema/release manifest and material inventory. The software checks
above are qualification evidence, not consumer adoption. Review and integrate the
core change, then independently qualify each exact consumer pin before admitting
the first research study. Test fixtures are software conformance only. The experiment package remains unpromoted; consumer
claim authority, mathematical review/novelty requirements and HOLD persist.
Length <=16 and existing group/k bounds remain. No scalable frontier coverage,
historical-script runner, external workers, generated code, provider calls,
second scheduler or self-promotion. Local filesystem/interpreter owners remain
trusted; this is not remote attestation or a hostile-code sandbox.

## Primary-source decisions (consulted 2026-11-15, Europe/Stockholm)

- SQLite transactions: https://www.sqlite.org/lang_transaction.html — use the
  existing atomic lease/completion authority; do not promise distributed WAL.
- Python JSON: https://docs.python.org/3/library/json.html — enforce byte bounds,
  duplicate-key and nonfinite-value rejection rather than permissive decoding.
- RFC8785: https://www.rfc-editor.org/rfc/rfc8785 — canonicalization is a defined
  protocol; sorted Python JSON is not automatically JCS. Bind raw bytes separately.
- Python OS: https://docs.python.org/3/library/os.html — exclusive installation
  and fsync underpin recoverable export, not an unaudited check-then-overwrite.

## Implementation review refinements

The persistent-effect boundary reserves database plus SQLite journal/WAL/SHM
sidecars and the export namespace before Store construction. Reject symlinks,
nonregular or multiply-linked DB/sidecars, orphan sidecars for a new DB, and any
input/source/output overlap. Export staging is exclusive and final install never
replaces a path. These are cooperative checks, not protection against concurrent
privileged filesystem mutation. Both CLI routes bind the exact requested task;
the legacy demo must not consume a queued study wrapper. Manifest question/limits
bind by exact encoding so JSON true cannot alias integer1.
