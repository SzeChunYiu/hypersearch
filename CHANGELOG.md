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
