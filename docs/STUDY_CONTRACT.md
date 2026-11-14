# Study schemas v1

Schemas are closed. Missing/extra fields, duplicate JSON keys, nonfinite values,
floating-point numbers and bool-as-int fail. Hashes use lowercase hex. Encoding
is sorted-key compact ASCII-escaped Python JSON, not RFC8785/JCS. Artifact hashes
cover raw bytes, not reserialized representations.

## hypersearch.study-manifest/v1

Fields: schema, study_id, question, limits, artifact_sha256. The last maps exactly
preregistration, claim_record, certificate to raw SHA256. No self-reference.

Question: adapter (ordinary-witness or multiwise-witness), integer list moduli,
k (1 ordinary; 1..16 multiwise), exact length (0..16), claim_type (exactly
lower-bound-witness), intended_bound (length+1), assumptions_sha256 (prereg digest).

Limits: db_max_attempts (positive SQLite integer; immutable DB-global ceiling),
timeout_seconds (1..60), commit_margin_seconds (1..60), max_certificate_bytes
(exactly65536). The timeout ceiling follows the bounded smoke route; timeout is
operational incompleteness, never mathematical completeness.

## hypersearch.study-bundle/v1

Fields: schema, study_id, consumer, instrument, question, artifacts, limits.
Manifest question/limits match exact encoding, not Python bool/integer equality.

Consumer: repository, commit (40hex), claim_id, claim_record_sha256,
preregistration_sha256, entrypoint (relative path), entrypoint_sha256.
Claim snapshot id must match; other claim semantics remain consumer-owned.
Entrypoint is hashed, never executed.

Instrument: repository, commit (40hex), release_version, api, verifier,
source_sha256. Origin is public Hypersearch. Source hashes cover all tracked
Python under src/hypersearch/ and governance/release.json. Omitting modules fails.
Runtime package/release/API/schemas/verifier must agree.

Artifacts maps exactly study_manifest, preregistration, claim_record, certificate
to records with path, bytes, sha256, base64. These paths and entrypoint are distinct
relative paths without traversal, symlinks or .git. Base64 is canonical.
Manifest/certificate<=64KiB each, preregistration/claim<=256KiB each, full execution
wrapper<=1MiB. Every artifact matches committed and working consumer bytes.
Group/k/verifier cannot override the hashed manifest.

## hypersearch.study-execution/v1

Fields: schema, kind, bundle, parent_receipt_sha256, replay_id.
Original kind requires null parent/replay ID. Replay requires trusted parent
SHA256 and nonempty ID. Task ID = study- plus SHA256 of the complete encoded
wrapper, frozen in the existing Store.

## hypersearch.study-receipt/v1

Fields: schema, execution (complete wrapper), task_id, outcome, outcome_sha256,
attempt, runtime, diagnostics, replay_matches_parent. No self-digest exists:
Store/export identity hashes the full receipt bytes.
Attempt: worker, fence. Runtime: python, implementation, core_commit, elapsed_ms
(integer). Diagnostics are bounded text. Replay comparison is boolean, original null.

Outcome: status, verification. Completed verifier outcomes carry verification;
failed/incomplete execution carries null. Existing closed verifier output schemas
are checked against the frozen question. Negative blocks are independently checked
for disjoint occurrence indices/zero sums. The whole outcome is the deterministic
comparison payload; runtime/diagnostics/attempt metadata are excluded. Its SHA256
is outcome_sha256.

Replay requires an external exact-byte commitment and validates schema, wrapper,
outcome/digest and runtime instrument before DB access. Store retrieval additionally
checks raw result digest/canonical encoding, task spec/digest, completed state
and task/result/receipt fence linkage. Local filesystem/Git/interpreter owners
remain trusted; these checks are not hostile-host authentication.
