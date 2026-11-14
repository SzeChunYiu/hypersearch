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
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m hypersearch run-study \
  --bundle /outside-source/bundle.json --consumer-root /pinned-consumer \
  --db /outside-source/tasks.sqlite --export /outside-source/receipts
```

Origins/HEADs, actual tracked bytes/modes and input/source hashes must agree.
Index hints cannot hide modified bytes. Source symlinks/unknown executable source
fail. Question/limits exactly match the hashed manifest, including JSON types.
Consumer entrypoint bytes are hashed, never executed. Dispatch allows only fixed
bundled verifiers; inputs cannot choose modules, callbacks or commands.

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
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m hypersearch replay-study \
  --receipt /outside-source/receipts/PREVIOUS.json \
  --expected-receipt-sha256 EXTERNALLY_COMMITTED_DIGEST --replay-id replay-2 \
  --consumer-root /pinned-consumer --db /outside-source/tasks.sqlite \
  --export /outside-source/replay-receipts
```

The expected digest comes from a separately committed manifest or trusted Store
record, never the receipt's own assertion. This is a trusted hash commitment,
not a signature/remote attestation. Replay freezes the original bundle plus parent
digest and replay ID in a separately hashed/charged task. Identical replay ID is
idempotent. Compare deterministic outcomes, excluding timings/runtime metadata.
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
registry/archive integrity, wrong-pin/dirty/wrong-task refusal, known-answer replay,
rollback and independent software review. Scientific promotion stays consumer-owned.
