# Repository and release lifecycle

## Layout and ownership

`src/hypersearch/` owns executable public interfaces, `tests/` owns known-answer and hostile fixtures, `examples/` contains public synthetic inputs, `governance/` owns machine-readable management metadata, `.github/` owns CI and review routing, and `docs/` explains architecture, operations and evidence. Consumer scientific state never lives in the harness repository. Add exact inventory entries for each tracked file, including manifests themselves; unregistered or missing tracked materials fail CI. Roles and administrative owners are not scientific approval credentials.

Do not create multiple authoritative copies. Link to the owning source. Supersede decisions through dated changes and preserve the Git history. Runtime failed experiments and receipts must be retained by the consumer's evidence store, not silently removed with a code refactor. External datasets/materials require origin, immutable version, digest, license/access conditions, retention and reproduction instructions; do not commit them without checking provenance and permissions.

## Branch and review discipline

Use `tooling/`, `study/`, `release/`, `fix/` or narrowly scoped feature branches. Keep infrastructure changes, scientific evidence and promotion separate. PRs identify affected contracts, consumers, migrations, tests and rollback. Stacked PRs explicitly identify their base dependency. Never force-push shared main, rewrite released artifacts or silently retarget a consumer.

CODEOWNERS routes review only. Required checks, stale-approval dismissal, non-author review, conversation resolution, restricted main/release-tag writes and disabled force push/deletion must be configured and independently observed in GitHub settings. The current tools do not establish those settings; their commissioning remains open. Do not call a policy document enforced branch protection.

## Versions and releases

The API manifest is `governance/release.json`; CI checks its version against package metadata. `development` is not a stable release. Consumers pin a full commit and required API/schema identities, even when a tag exists. Any two commits with the same development version remain different instruments. Once stable releases begin, use semantic versioning, immutable tags/artifacts, explicit public API and changelog, tested schema migrations, deprecation windows and consumer conformance receipts.

Before release: reproduce tests on supported runtimes; inspect source/license/disclosure; identify compiler/build/runtime dependencies and build provenance; test clean installation and at least one consumer; collect independent review; record artifact digest and rollback target; verify repository protections. Current source-run CI does not certify reproducible package builds, signed releases, dependency vulnerability scanning or a SLSA level. The permissive setuptools build dependency remains a packaging/release blocker; the tested consumer route runs pinned stdlib source without installing packages.

## Upgrade and rollback

A pin update is a dedicated consumer PR. Test old and candidate instruments against the same frozen fixtures, wrong-pin/dirty-input refusal, and return to the old pin. Existing studies retain their original evaluator and input identities. Re-evaluation produces a new receipt linked to the old one. On verifier defects, record affected versions and invalidate/recheck dependent evidence prospectively; do not edit historical claims into apparent validity.

## Retention and disaster recovery

Back up Git, consumer artifacts and coordinator state separately. Git is not a backup of external compute jobs or unfinished liabilities. Restoration must reconcile running effects and fence stale workers. Current local prototype has no commissioned cross-machine recovery or retention service. Deleting the whole evidence directory must never turn a check into a pass.

Primary guidance: [SemVer](https://semver.org/), [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [SLSA provenance](https://slsa.dev/spec/v1.2/build-provenance). Consulted 2026-11-14; these inform policy, not a compliance certification.
