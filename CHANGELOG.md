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

- Study and review commands refuse any launch other than
  `-B -S -P -X pycache_prefix=<new empty directory>`, and any import-path entry
  that is not the pinned `src` or the interpreter's own library. Previously an
  ignored cache, or an ignored standard-library-named file in the launch
  directory, executed while source hashes passed, and a false witness could be
  committed and exported as VERIFIED_WITNESS.
- Admission refuses any entry named `__pycache__` under the pinned `src` tree
  and any redirected-cache entry for a pinned module.
- An unexpected failure exits 2. Exit 1 is reserved for a completed refutation.
- **Consumer migration:** a consumer that launches these commands must add
  `-P`. A core checkout holding caches, including ones written by running the
  tests or demo without `-B`, is refused until they are deleted. In-process
  callers are not subject to the launch contract and own their own boundary.
- No schema, verifier, API or version change; the exact commit identifies the
  instrument. Adoption is a consumer pin PR with that consumer's own controls.
