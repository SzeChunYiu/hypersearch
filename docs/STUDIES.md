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
refuse anything else before any database, grant or export effect:

| Flag | Refused without it because |
|---|---|
| `-P` | the working directory would be on the import path |
| `-S` | site directories and their startup hooks would be loaded |
| `-B` | the run would write bytecode caches |
| `-X pycache_prefix=<new empty directory>` | adjacent caches would be consulted |

The cache prefix must not exist yet or must be an empty directory; `-i` and
`PYTHONINSPECT` are refused because they replace the exit code. Every
import-path entry must be the pinned `src` or the interpreter's standard
library (not its site directories). Admission also refuses any entry named
`__pycache__` under the core `src` tree, whatever its type, and any
redirected-cache entry for a pinned module. A checkout that has run the unit
tests or the demo without `-B` holds such caches; delete them first. The
installed `hypersearch` console script cannot satisfy `-S` and is not a
supported way to run these commands.

Limits. The flag and working-directory checks run before the package's own
imports, though after the interpreter's own start-up imports; the remaining
checks run inside modules that are already imported.
They catch honest launch mistakes. They are not a control against hostile
files under a launch that does not conform: such a file can run first and
forge what the checks read. Under the required launch from a checkout whose
ignored files an adversary controls, review found no way to execute foreign
code and still obtain a receipt. A refused launch without `-B` still leaves
caches behind. Code that imports the package in-process owns its own launch
boundary. Interpreter startup, the standard library and the filesystem owner
remain trusted. Unexpected failures inside the command exit 2; failures of
the interpreter itself, such as a wrong `PYTHONPATH`, exit 1 with nothing on
stdout.
**Consumers should require the printed `outcome_status`, not the exit code
alone.**

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
Stale completion cannot commit/export. No CPU/memory/dollar budget or hostile
code sandbox is claimed; the usage printed since 0.8.0 is a measurement, not a limit.

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
A start refused before any lease prints `"execution": "not_started"` with a
`reason`, the database's `budget` and the `task_state` (since 0.7.1); see
[pinned programs](PROGRAMS.md#outcomes).

## Resource usage in the printed result — since 0.8.0

A completed execution, whatever its outcome status, also prints

```json
"usage": {"wall_milliseconds": 1234, "cpu_milliseconds": 1180, "max_rss_kilobytes": 24816}
```

`not_rerun` and `not_started` results carry no `usage`. The figures describe
the host, so they are **not in the receipt**, are not compared by a replay
and are not printed again by `not_rerun`: keep the printed line if they are
needed. They are integers because this JSON dialect has no other number.

- **What is measured** is the route's one child process: the verifier child
  of a study or census, the program of a pinned-program task. Wall time runs
  from just before that child is started until it has been waited for. The
  end is found by polling every 50 milliseconds at most, so wall time can
  be up to that much late: it is coarse for short runs. CPU time is not.
  Source checks, the database and the export are outside it; the receipt's
  `elapsed_ms` is a wider interval.
- `cpu_milliseconds` is user plus system CPU time of that child and of the
  descendants it waited for itself. **A process the child started and did
  not wait for is not counted**, whether or not it was killed with it.
- `max_rss_kilobytes` is the peak resident set size, in kilobytes on Linux
  (macOS reports bytes, which are converted; not tested there). A program
  is reaped with `wait4`, so its figure is its own: the largest single
  process among it and the descendants it waited for, not a sum. A verifier
  child is reaped by `subprocess.run`, which leaves only the process-wide
  mark over every child the command has waited for, its `git` checks
  included; the figure is printed when this run raised that mark and is
  `null` when it did not, because then it is not this child's.
- **Linux carries the peak across `exec`**: a child's figure starts from the
  memory it inherited from the launching process when it was started, about
  twenty megabytes for this command. A value near that is the floor, not a
  measurement of the child.
- A timeout or a failure reports what the child used until it was killed.
  When no child was waited for, the figures are 0, 0 and `null`.
- A caller that runs several executions in one process shares the
  verifier-child counters between them.

Wall time far above CPU time for a single-threaded computation means the host
was busy or the child waited; a timeout with CPU time near the limit means
the computation is slow. See getrusage(2) and wait4(2).

## Checking an export — since 0.8.0

`check-export` re-verifies receipt directories of any of the three routes
without running anything, and can hold them against outcomes registered
beforehand. See [checking exported receipts](CHECK_EXPORT.md).

## Qualification

Development0.3.0 adds APIv1 schemas. Verifier bounds/IDs stay unchanged: ordinary
order<=64/length<=16; multiwise order<=1,000,000/length<=16/k<=16. No frontier
completeness follows. Before research, require reviewed core, consumer pin adoption,
registry/archive integrity, wrong-pin/dirty/cached-bytecode/wrong-task refusal, known-answer replay,
rollback and independent software review. Scientific promotion stays consumer-owned.
