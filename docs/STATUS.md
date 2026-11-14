# Status — 2026-11-14

## Observed implementation

- Foundation commit f7254533a9310060bde7f045e7ba89b12d520073: 18 tests and demo passed in GitHub Actions on Python 3.11/3.12/3.13.
- Governed-adoption development: 33 tests passed locally on Python 3.12.14, including inventory/version checks, mutable-action refusal, exact multiwise verification and task binding.
- Multiwise C2 known-answer example verifies only D_2(C2) >= 4. An assignment-based tiny oracle cross-checks the subset-packing algorithm. No formal proof, independent-team replication or novel theorem is claimed.
- Current management version is 0.2.0 development. Exact source pins distinguish this from the original 0.1.0 foundation.
- Public implementation contains no private research material. Consumer integration is a separate, pinned reviewable change; consumer CI/commissioning evidence belongs with that change.

## Admission correction — local qualification

- Baseline `d7930513801217b8ff3004d0a0baab0147781238` admitted malformed
  demo inputs before validation: six invalid-input fixtures created database
  files, and an invalid request could acquire earlier valid pending work.
- The correction validates before store construction and shares the adapter's
  bounded-input validator with execution. On Python 3.12.14, all 36 tests,
  the governance check, fresh README demo, and multiwise example passed.
- Regression controls require unchanged existing task/event/result/attempt
  state after rejection. Admitted execution failures still consume an attempt
  and retain their failure record; these are not refunded or erased.
- This is a software admission fix, not a verifier-semantic or schema change.
  Development version remains 0.2.0; the exact commit identifies the changed
  instrument. Existing consumers and in-flight studies retain their old pins.
  Independent review and actual-consumer adoption are separate gates.

## Readiness boundaries

Inventory CI, package-version consistency and pinned action references are implemented. Remote required checks, branch/ruleset protection, release-tag immutability and independent reviewer authority have not been commissioned or verified. CODEOWNERS alone does not enforce them. GitHub ruleset listing returned an empty list; the classic branch-protection read returned HTTP 403 (integration lacks administration access). No protection settings were changed.

This is not a stable production release or a deployed autonomous scientist. No authenticated fleet, generated-code sandbox, external-effect fencing, protected empirical evaluation or formal-prover adapter is commissioned. Current mathematics remains bounded certificates; it cannot execute the complete large rank-three/multiwise frontier programme.

Twin-system development shares contract IDs and tested generic improvements. Private pipeline compatibility and distributed-runtime parity require separate actual-consumer evidence. Preserve all consumer promotion holds and original frozen study pins.

See docs/governance/INDEX.md for management ownership and docs/ROADMAP.md for unfinished phases.
