# Lean source snapshot preparation

Experimental implementation toward issues #2 and #3 and the selected-candidate
boundary of #24. It is not a registered verifier, executable route, receipt
schema, formal certificate, or authorization to run research. The release's
supported route/schema lists remain unchanged.

`lean_snapshot.validate_snapshot` validates the closed draft envelope
`hypersearch.lean-source-snapshot/draft1`: `schema` and `files`, where each file
uses the existing `path`, `bytes`, `sha256`, canonical `base64` artifact encoding.
It returns path-to-byte mappings without creating files or loading source.
`snapshot_digest` hashes the sorted path/byte-count/content-digest list under
the draft schema. File-list permutation preserves identity; any byte or path
change changes identity. It uses the project's JSON encoding, not RFC8785.

Bounds: 128 files, 262144 bytes each, 1048576 total decoded bytes. Only `.lean`
files and root `lakefile.toml`, `lean-toolchain`, `lake-manifest.json` are admitted.
Names use a restricted portable ASCII spelling; hidden components, traversal,
compiled artifacts, case collisions, duplicates and file/directory prefix
collisions refuse. Contents must be UTF-8 without NUL or carriage returns.
Unicode Lean syntax is allowed. This is a deliberately restricted draft.

Validation does not establish that imports are complete, that the toolchain
declaration is truthful, that dependencies are available offline, that the
source elaborates, or that a theorem holds. Lean source and lakefiles can execute
code during elaboration/build. They must never be evaluated in the harness's
parent process. No dependency network access, extraction, subprocess execution,
Store grant or claim effect is implemented by this helper.

The future route must separately bind evaluator-owned target and axiom policy,
trusted toolchain/checker/runtime identities, challenge and dependency snapshots,
immutable source-to-export construction, all required checks, resource limits,
failure receipts and replay. Matching metadata is not producer authentication.
The existing pinned-program route must not be relabelled as formal verification.

Synthetic tests cover byte and field tampering, bool/integer confusion, path
attacks, collisions in either ordering, size limits, text encodings, deterministic
identity and no mutation of inputs. A comment-only file is intentionally valid:
the validator must not imply proof acceptance. Independent review and consumer
qualification are pending; no scientific claim or issue completion follows.
