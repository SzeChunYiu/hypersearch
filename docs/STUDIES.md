# Frozen supplied-certificate studies — development contract

This route checks bounded supplied witnesses using trusted bundled adapters.
It does not launch research agents, run historical scripts, prove upper bounds,
accept claims, clear promotion holds or establish novelty.

## Inputs and authority

Commit the consumer study manifest, preregistration, claim snapshot and supplied
certificate first. Assemble a `hypersearch.study-bundle/v1` from that commit,
naming the consumer entrypoint and exact core checkout/source hashes. Keep the
transport bundle outside source checkouts to avoid self-referential commit hashes.
See [schemas](STUDY_CONTRACT.md) and
[design](plans/2026-11-15-frozen-supplied-certificates.md).
`tests/study_fixture.py` constructs wholly synthetic pinned consumers.

```sh
CACHE=$(mktemp -d)  # private and empty; never a reused or shared cache directory
PYTHONPATH=src python -B -S -P -X pycache_prefix="$CACHE" -m hypersearch run-study \
  --bundle /outside-source/bundle.json --consumer-root /pinned-consumer \
  --db /outside-source/tasks.sqlite --export /outside-source/receipts
```

Origins/HEADs, actual tracked bytes/modes and input/source hashes must agree.
Index hints cannot hide modified bytes. Source symlinks/unknown executable source
fail. Question/limits exactly match the hashed manifest, including JSON types.
Consumer entrypoint bytes are hashed, never executed. Dispatch allows only fixed
bundled verifiers; inputs cannot choose modules, callbacks or commands.

## Executed code, not only source bytes

Source hashes bind files, not what the interpreter loads. Two things can put
other code in front of a pinned module while `git status` stays clean:

- **A bytecode cache.** An ignored `__pycache__` entry that is unchecked-hash,
  or stale with a recorded mtime/size that still match, is imported in place of
  the pinned file. Disabling bytecode writes does not disable reads.
- **The import path.** `python -m` puts the working directory first, so an
  ignored standard-library-named file there is imported before the real one;
  site directories and ambient `PYTHONPATH` entries can do the same.

The study and review commands therefore **require** the launch shown above and
refuse anything else before any effect:

| Flag | Refused without it because |
|---|---|
| `-P` | the working directory would be on the import path |
| `-S` | site directories and their startup hooks would be loaded |
| `-B` | the run would write caches into the checkout |
| `-X pycache_prefix=<new empty directory>` | adjacent caches would be consulted |

Every import-path entry must then be the pinned `src`, the interpreter's own
library, or absent. Admission also refuses any entry named `__pycache__` under
the core `src` tree, whatever its type, and any redirected-cache entry for a
pinned module. A checkout that has run the unit tests or the demo without `-B`
holds such caches; delete them first.

Limits. These checks run inside modules that are already imported, so they
cannot authenticate themselves: a launch that reads adjacent caches can be
handed a replaced admission module. The required launch is what prevents that,
and a launch chosen by an adversary is outside this contract. Code that imports
the package in-process, instead of using these commands, owns its own launch
boundary. Interpreter startup, the standard library and the filesystem owner
remain trusted. An unexpected failure exits 2, never 1.

## One effect-admission boundary

Before Store construction, validate inputs and every persistent-effect path:
DB, SQLite `-journal`/`-wal`/`-shm`, export directory and staging/final namespace.
These cannot overlap source roots/input files. Symlink or multiply-linked DB/
sidecars fail; orphan sidecars for a new DB fail. Export staging is exclusive,
final installation never replaces an existing path. This is cooperative local
filesystem safety, not protection against concurrent privileged mutation.

Demo/study CLI acquires only its exact task. Generic Store queue order remains;
there is no second scheduler. `db_max_attempts` is DB-global, not per study, and
must match the database's original ceiling. Every grant remains charged after
failure/timeout/lost reply. Lease duration is timeout plus explicit commit margin.
Stale completion cannot commit/export. No CPU/memory/dollar accounting or hostile
code sandbox is claimed.

## Outcomes and recovery

Only completed schema-checked verifier output yields VERIFIED_WITNESS or
REFUTED_WITNESS. A verified length-L witness supports only D or D_k >= L+1.
Refuting one witness says nothing about other possible witnesses. Timeout is
INCOMPLETE; process/format errors are EXECUTION_FAILED. Neither has a bound or
mathematical negative verdict.

Store completion atomically records the full frozen wrapper and outcome. Export
follows fenced commit, named by SHA256 of exact receipt bytes. Repeat requests
say `not_rerun`, return the same receipt and add no charge. This recovers interrupted
export. Corrupt files or task/result identity/fence mismatches fail, never rewrite.

## Replay and upgrade

```sh
PYTHONPATH=src python -B -S -P -X pycache_prefix="$CACHE" -m hypersearch replay-study \
  --receipt /outside-source/receipts/PREVIOUS.json \
  --expected-receipt-sha256 EXTERNALLY_COMMITTED_DIGEST --replay-id replay-2 \
  --consumer-root /pinned-consumer --db /outside-source/tasks.sqlite \
  --export /outside-source/replay-receipts
```

The expected digest comes from a separately committed manifest or trusted Store
record, never the receipt's own assertion. This is a trusted hash commitment,
not a signature/remote attestation. Replay freezes the original bundle plus parent
digest and replay ID in a separately charged task. Replay ID is unique within
one database and atomically bound to the entire wrapper. Same ID/same wrapper is
idempotent; changed parent/bundle conflicts before grant. A different ID is an
independent attempt. Receipt execution_sha256 binds the complete wrapper. Compare deterministic outcomes, excluding timings/runtime metadata.
A second agent/host is not external mathematical refereeing. Use a separate replay
export directory because input/output overlap is prohibited.

New evaluator = reviewed study revision and consumer pin, not implicit upgrade.
Rollback restores future execution configuration and preserves historical evidence.
Exits: 0 verified; 1 completed witness refutation; 2 refusal, unavailable grant,
incomplete/failed execution or replay mismatch. Always inspect receipt scope.

## Qualification

Development0.3.0 adds APIv1 schemas. Verifier bounds/IDs stay unchanged: ordinary
order<=64/length<=16; multiwise order<=1,000,000/length<=16/k<=16. No frontier
completeness follows. Before research, require reviewed core, consumer pin adoption,
registry/archive integrity, wrong-pin/dirty/cached-bytecode/wrong-task refusal, known-answer replay,
rollback and independent software review. Scientific promotion stays consumer-owned.
