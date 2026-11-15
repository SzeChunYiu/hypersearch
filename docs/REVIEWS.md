# Frozen external expert reports — 0.4.0 development

This route governs **task admission, ownership and report provenance**. It does
not evaluate mathematical correctness, authenticate an expert, establish
independence or promote claims. Every receipt says `NOT_FORMALLY_VERIFIED` and
`claim_authority=none`; supports is an author-provided assessment, never proof.
Only a separately reviewed consumer may use this experimental interface.

## Ordered native-session handoff

Use the same local Python module and immutable core checkout for all commands.
The consumer and core must be distinct clean Git checkouts. Sources, inputs and
protocol are frozen before registration. Database and exports live outside both.

```sh
run() { python -B -S -X pycache_prefix="$(mktemp -d)" -m hypersearch "$@"; }
run register-review --bundle bundle.json \
  --consumer-root consumer --db reviews.sqlite --export receipts
run grant-review --bundle bundle.json \
  --consumer-root consumer --db reviews.sqlite --export receipts > grant.json
```

Every command uses a private empty bytecode prefix: source pins do not bind an
ignored cache that the interpreter would load instead. Admission also refuses
any cache for the pinned core; see [executed code](STUDIES.md#executed-code-not-only-source-bytes).

Only after a successful persisted grant may the orchestrator dispatch an
already authorized native expert session with the frozen bundle and grant.
The orchestrator records its actual contributor/delegation lineage in the bundle
before registration. Hypersearch does not launch sessions, expose credentials,
make provider calls, execute report code, or introduce a second scheduler.

```sh
run submit-review --bundle bundle.json --grant grant.json \
  --report report.json --consumer-root consumer --db reviews.sqlite --export receipts
run recover-review --bundle bundle.json \
  --consumer-root consumer --db reviews.sqlite --export receipts
```

Recovery reads the existing completed result and exports its exact receipt; it
never grants work. Duplicate completion is rejected. Expired/superseded reports
are rejected without export, while grants remain charged. The caller retains
refused report bytes; do not discard them or relabel them accepted. No automatic
renewal exists. A new grant after expiry consumes another attempt.

The database counts acquisitions, not money/tokens/CPU. Grants cannot fence the
external session itself; the receiver fences only result acceptance. Local
filesystem owners, interpreter and orchestration labels remain trusted.

## Closed schemas

Encoding is the existing bounded strict JSON encoding, not JCS. Duplicate keys,
noninteger JSON numbers, bool-as-integer, extra fields and size violations fail.
All artifact records contain path, bytes, sha256 and canonical base64; hashes
cover raw bytes. Paths are unique, relative and inert, never executed.

`hypersearch.review-bundle/v1` contains schema, review_id, question, role,
reviewer, lineage, exclusions, parent, consumer, instrument, artifacts, protocol,
limits. Question and protocol are immutable parts of the Store specification.
Protocol names an included artifact. At most sixteen input artifacts of 256KiB
each; the complete bundle is at most 1MiB.

Consumer contains repository and full commit. Every input must match committed
and current consumer bytes. Instrument contains repository, commit,
release_version, api and source_sha256: exactly all tracked src/hypersearch
Python plus governance/release.json. The running version must match; an old
instrument is never silently upgraded. A frozen 0.3 certificate study continues
on its original 0.3 checkout; its existing APIs and authority remain unchanged.

Role is proof-author, literature-reviewer, hostile-reviewer or methodology-reviewer.
Reviewer must occur in lineage. Review roles refuse any overlap of lineage and
excluded contributor/delegation labels; authors may author but are not counted
as independent reviewers. Labels are declarations, not signatures or verified
identities. A dishonest rename cannot be detected by this cooperative system.

Parent is null, or task_id plus receipt_sha256. For nonnull parent supply
`--parent-receipt` on every operation. Its actual bytes must match that externally
frozen digest, validate as a review receipt and bind the named parent task.
This checks the immediate referenced receipt, not authenticity of its host or
recursive scientific validity of all ancestors. A citation URL is descriptive
metadata, not automatically retrieved or authenticated primary evidence.

Limits contain db_max_attempts and lease_seconds (1..86400). review_id determines
a stable namespaced task key; Store atomically binds it to the complete bundle.
Changed source, question, protocol, role or parent under that ID is a conflict.
A changed programme requires a fresh ID and explicit lineage.

`hypersearch.review-grant/v1` contains schema, task_id, bundle_sha256, worker,
fence and expires_at. Expiry is the exact string representation of the Store
float timestamp, avoiding float values in strict JSON. A grant envelope is not
authority: submission checks the real Store row and atomic Store.complete.

`hypersearch.review-report/v1` contains schema, task_id, bundle_sha256,
grant_sha256, reviewer, role, outcome, findings_kind, report, evidence.
Findings_kind must be author_provided_not_independently_established. Outcome is
supports, objects, inconclusive, failed or incomplete. Failures are operational
reports, not negative mathematical verdicts. Report is a raw artifact; evidence
is up to eight artifacts. Whole report <=1MiB; each artifact <=256KiB.
New literature can be preserved as output evidence, without changing the frozen
question; material expansion requires another registered task.

`hypersearch.review-receipt/v1` embeds full bundle, grant and report, report hash,
verification, claim_authority and independence=declared_not_authenticated.
Whole receipt <=3MiB. Store result identity hashes the entire canonical receipt.
No self-hash exists. Export uses that digest as filename with no overwrite.

## Acceptance and boundaries

Tests cover synthetic CLI handoff, actual lease receiver refusal, expiry,
reclamation, duplicate/racing completion, mismatch/strict parsing, role conflict,
source corruption, DB aliasing, negative preservation, parent binding and export
recovery. The full existing suite and governance gate remain required.
Independent review and consumer commissioning remain additional gates.

This is adapted from existing Store and frozen-study primitives, informed by
[SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html) and
[W3C PROV-DM](https://www.w3.org/TR/prov-dm/), read 2026-11-15. It makes no PROV
conformance claim. Consumer proof/literature policies decide what evidence is
sufficient; this administrative route alone establishes no mathematical result.
