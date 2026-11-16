# Status — 2026-11-14

## Observed implementation

- Foundation commit f7254533a9310060bde7f045e7ba89b12d520073: 18 tests and demo passed in GitHub Actions on Python 3.11/3.12/3.13.
- Governed-adoption development: 33 tests passed locally on Python 3.12.14, including inventory/version checks, mutable-action refusal, exact multiwise verification and task binding.
- Multiwise C2 known-answer example verifies only D_2(C2) >= 4. An assignment-based tiny oracle cross-checks the subset-packing algorithm. No formal proof, independent-team replication or novel theorem is claimed.
- Current management version is 0.5.0 development. Exact source pins distinguish this from the original 0.1.0 foundation.
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
  At that correction, development version remained 0.2.0; the exact commit identifies the changed
  instrument. Existing consumers and in-flight studies retain their old pins.
  Independent review and actual-consumer adoption are separate gates.

## Frozen supplied-certificate route — implementation under review

The 0.3.0 source adds closed bundles, exact-task grants, bounded verifier children,
full receipts and external-digest replay. On Python 3.12.14, all 61 tests,
governance validation, fresh README demo and multiwise example passed. Direct
CLI-file execution runs all eight CLI tests. Only public synthetic known-answer/
refusal fixtures were used. Hostile review reproduced manifest bool/integer
aliasing, SQLite sidecar/input collision, source hardlink mutation and mixed-queue
consumption; regression tests now refuse each before the corresponding effect.
A later valid-parent replay-ID substitution was also reproduced: DB-scoped replay
keys now atomically bind one full wrapper. Changed-parent, changed-bundle and
concurrent-conflict regressions pass without additional grants on the losing path. Consumer adoption, independent release qualification
and scientific admission remain separate. See docs/STUDIES.md and
STUDY_CONTRACT.md. No historical scripts or private material are included.

## Readiness boundaries

Inventory CI, package-version consistency and pinned action references are implemented. Remote required checks, branch/ruleset protection, release-tag immutability and independent reviewer authority have not been commissioned or verified. CODEOWNERS alone does not enforce them. GitHub ruleset listing returned an empty list; the classic branch-protection read returned HTTP 403 (integration lacks administration access). No protection settings were changed.

This is not a stable production release or a deployed autonomous scientist. No authenticated fleet, generated-code sandbox, external-effect fencing, protected empirical evaluation or formal-prover adapter is commissioned. Current mathematics remains bounded certificates; it cannot execute the complete large rank-three/multiwise frontier programme.

Twin-system development shares contract IDs and tested generic improvements. Private pipeline compatibility and distributed-runtime parity require separate actual-consumer evidence. Preserve all consumer promotion holds and original frozen study pins.

See docs/governance/INDEX.md for management ownership and docs/ROADMAP.md for unfinished phases.

## External expert-report workflow — 0.4.0 development, 2026-11-15

Implemented register/grant/submit/recover review commands on the existing Store.
The externally authored report binds frozen inputs, source pins, declared role
lineage and an actual current Store lease; all receipts explicitly retain
NOT_FORMALLY_VERIFIED and no claim authority. No model launcher, provider call,
arbitrary-code execution or independent authentication was added.

Author qualification on Python 3.12.14: 76 tests passed (61 existing, 15 review),
tracked-material governance passed, fresh README demo and multiwise example
passed. Review tests include actual CLI handoff after persisted grant,
concurrent completion, expired/reclaimed leases, source corruption, role
conflicts, parent digest binding, negative reports and recoverable exports.
All new fixtures are public synthetic data. The initial version-bump test run
exposed a hardcoded fixture version; fixtures now use the running version while
production admission still requires exact instrument/version pins.

These are implementation-author checks, not independent qualification.
Independent code/receiver review, public CI and actual-consumer commissioning
remain required before adoption. Existing 0.3 studies retain their original
pins. No research was executed and no scientific claim was promoted.

## Pure shadow director — 0.5.0 development, 2026-11-15

Initial issue #16 software increment: closed frozen observations and policies
produce deterministic shadow recommendations without Store access, grants,
filesystem effects or provider calls. Declared gain/cost values are hypothetical;
seeded hash order is not an exactly uniform random baseline. No optimality,
calibrated VOI, scientific efficacy or autonomous execution is established.

Author checks on Python 3.12.14: 87 tests passed (76 existing, 11 new director
conformance tests), local governance passed, fresh README demo and bounded
multiwise example passed. Only synthetic/known-answer software fixtures ran.
Existing study/review code and tests are unchanged. Independent review, public CI
and any consumer adoption remain pending. Original frozen evaluator pins persist.

See [director contract](DIRECTOR.md) and [design alternatives](DIRECTOR_DESIGN.md).
No research HOLD changes; issue #16 remains open for separately specified work.

### Pre-merge policy correction

Author candidate da28c40 is superseded: shared positive-gain filtering had
prevented exploratory policies from selecting zero-immediate-gain prerequisites.
Legality now depends only on snapshot gates. Supplied/hash order may select any
legal declared gain; greedy ratio explicitly skips nonpositive gain.
Duplicate frozen task digests refuse even under distinct candidate IDs.
Costs are explicitly potentially incomplete declared estimates, not measured totals.
The corrected synthetic prerequisite and duplicate-task controls pass.

## Executed-code admission correction — 2026-11-15

Reproduced at main `8dfce976f80fabd53e79985de1b6422de26f575a` through the actual
CLI on Python 3.11 and 3.13: with `git status` clean and every source hash
matching, an ignored cache for a parent-process module executed. Unchecked-hash
caches and stale timestamp caches with a matching header were both loaded. A
cache for `study_outcomes` turned a false synthetic witness (honest outcome
REFUTED_WITNESS, exit 1) into a committed, exported VERIFIED_WITNESS receipt
with exit 0 carrying the pinned commit and source hashes. `study_paths.py` is
byte-identical at `06e9c46` and `1ca5ea0`; the review route did not exist at the
latter. The verifier child was unaffected: it already used a private prefix.

First correction (`d6d0cbe`): one shared boundary refusing caches for the pinned
core, with a documented private-prefix launch. A fresh-context adversarial
review of that commit found it insufficient:

- **Blocking.** Under the documented launch, an ignored sourceless
  `argparse.pyc` in the launch directory still executed and produced the false
  VERIFIED receipt, because `python -m` puts the working directory first on the
  import path. This predates the change; the documented launch did not close it.
- A named pipe or an unlistable directory at `__pycache__` passed the check.
- An import path through a directory of symlinks to the pinned files bypassed
  the redirected-cache check.
- The review launch snippet lacked `PYTHONPATH`; crashes exited 1, the code
  reserved for a completed refutation; a checkout under a directory named
  `__pycache__` was refused.

Second correction (`c953154`): study and review commands refuse unless started
with `-B -S -P -X pycache_prefix=<new empty directory>` and unless the import
path holds only the pinned `src` and the interpreter's library. Any entry named
`__pycache__` under `src` is refused whatever its type. Unexpected failures
exit 2.

The same reviewer re-attacked that commit and found nothing blocking: every
first-round finding was closed under the required launch, and no way was found
to execute foreign code and still obtain a receipt when the launch is exactly
the documented one and the adversary controls only ignored files. It did find:

- the cache prefix was not checked to be empty, so a reused prefix holding a
  standard-library cache produced the false receipt with all four flags;
- `-i` or `PYTHONINSPECT` turned a refusal into exit 0 or 1;
- the checks ran after `argparse` was imported, so a hostile file in the launch
  directory under a non-conforming launch could forge what they read;
- site directories under the standard-library directory were accepted, an
  absent path entry was trusted after imports, and an interpreter with a zip
  standard library was refused; the review snippet used relative operands.

Third correction (this change): the prefix must be absent or empty; inspect
mode is refused with a hard exit 2; the flag and working-directory checks run
in `__main__` before the package's own imports; site directories and absent
entries are no longer accepted and the standard-library zip is. Eleven
regression tests. Measured by the reviewer on the ten-test version: eight
fail against the first correction and three against the second. Against the
unfixed commit the current test module cannot import; the original five-test
version failed four of five there.

A third, bounded review of that commit found nothing blocking and four small
items, fixed here: the phrase "before any non-frozen import" was false (the
interpreter's own start-up imports precede it, so a hostile file under a
non-conforming launch can still win); a launch from a deleted working
directory crashed with exit 1; `--` before the command skipped the early
check; two statements in this file and the changelog were imprecise.

Limits that remain. The later checks run in already-imported code. They catch
honest mistakes; they are not a control against hostile files under a launch
that does not conform, and a replaced admission module under such a launch
still wins. Interpreter-level failures exit 1 without output. A launch chosen
by an adversary is outside the contract. Interpreter startup, the standard
library and the filesystem owner stay trusted. In-process callers bypass the
launch contract by design. `demo` and `verify` print source hashes without
this admission.

Evidence class: author checks plus two rounds of fresh-context review by a
session the author started. That is declared separation, not independent
certification. The third correction has author checks only. Counts are in the
pull request. Public CI and consumer pin adoption are separate gates.
**Consumers launching these commands must add `-P`** and should check the
printed `outcome_status`. No schema, verifier, API or version change. Existing
studies keep their pins. No research executed.

## Newer frozen routes — status kept with each route

- Exhaustive census tasks (0.6.0 development): see the status section of
  [CENSUS.md](CENSUS.md).
- Pinned-program tasks (0.7.0 development): see the status section of
  [PROGRAMS.md](PROGRAMS.md).
- Export check and resource usage (0.8.0 development): see the status
  section of [CHECK_EXPORT.md](CHECK_EXPORT.md) and the usage section of
  [STUDIES.md](STUDIES.md). Reviewed twice by one separate session started
  by the author (defects found and fixed, then confirmed); not independent
  certification.
- Stopping a launch and `abandon-attempt` (0.9.0 development): see the
  status section of [STOPPING.md](STOPPING.md). Author checks only.
- Admitted exploration tasks (0.10.0 development): see the status section
  of [EXPLORATION.md](EXPLORATION.md). Author checks only.

None of these executes research here, promotes a claim or lifts a consumer hold.
