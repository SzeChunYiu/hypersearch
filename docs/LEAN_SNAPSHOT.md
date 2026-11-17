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

## Frozen question and candidate binding

`lean_request.question_digest` validates a separate evaluator-owned draft
question: challenge and solution module names, target declaration, challenge
snapshot digest, dependency snapshot digest, runtime digest, evaluator digest,
an empty allowed-axiom list, and exact binary digests for all six checkers
(Lean default/paranoid, lean4lean, Nanoda, con-leche and con-ron).
The question's identity covers every field. This draft supports only the empty
axiom policy; it does not silently broaden that policy for imported libraries.

`bind_candidate` requires the externally frozen question digest as a keyword
argument. The candidate envelope contains only its schema, question digest and
source snapshot. A candidate cannot supply the expected digest, claim proof
acceptance, replace checker settings or change the target. Even if it recomputes
a digest for a changed question, the external frozen identity must still match.
The challenge snapshot must match the frozen digest and both named module
source files must exist in their respective snapshots. Each module is assumed
to map from `A.B` to `A/B.lean`; custom Lake source-directory layouts are not
supported by this draft.

The returned record contains identities only. A changed solution creates a new
candidate identity under the same question, even if it contains no proof. It
must subsequently be checked against the evaluator's actual challenge; syntactic
presence of a file or declaration name is not proof of its meaning. The helper
does not check declaration existence or parse Lean source.

The caller must obtain the expected question digest from its trusted task
authority. Supplying both an attacker-controlled question and its digest defeats
that boundary. These pure helpers neither authenticate the caller nor freeze a
Store task, and the dependency/runtime/checker digests are required references,
not measurements of installed bytes. A complete route must enforce these at
the receiver, freeze target selection before checking, and bind source-to-export
construction and all verifier outcomes before it can emit any proof receipt.

Both draft schemas remain unregistered and have no CLI route. Existing study
pins, release schemas, execution authority and scientific claim scopes are
unchanged. Tests cover substituted goals/runtime/imports/checkers, missing
checkers, extra axioms, forged acceptance fields, wrong challenge bytes, missing
module source, unsafe identifier syntax, and candidate identity changes.
