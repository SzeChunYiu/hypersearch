# Checking exported receipts — 0.8.0 development

`check-export` re-verifies directories of exported receipts of one frozen
route (supplied-witness studies, censuses or pinned programs) and, if asked,
holds them against outcomes a consumer wrote down before execution. It does
the mechanical part of a review of a family of studies: every file is intact,
every replay has its original, and what was printed is what was registered.

It is **read-only**. It opens no database, runs no verifier and no program,
and writes nothing. It accepts no claim, assesses no novelty and lifts no
consumer hold. Whether the registered outcomes were the right ones to
register, and whether a program is correct, stay with the consumer's review.

## Running it

The launch is the one [frozen studies](STUDIES.md) require, for the same
reason: the validators that run must be the pinned ones.

```sh
CACHE=$(mktemp -d)  # private and empty
PYTHONPATH=src python -B -S -P -X pycache_prefix="$CACHE" -m hypersearch check-export \
  --route program --export /outside-source/receipts --export /outside-source/replay-receipts \
  --expected /pinned-consumer/expected.json
```

`--route` is `study`, `census` or `program`. `--export` names a receipt
directory and may be repeated; originals and replays are normally in
different directories. `--expected` is optional.

Exits: **0** when `ok` is true; **1** when any problem was found; **2** when
the command line, the launch or the expected file is refused, with nothing on
standard output. An interpreter-level failure also exits 1 without output, so
require the printed `"ok": true`, not the exit code alone.

## What is checked

Every entry directly in each directory is looked at. There is no recursion.
An entry whose name starts with a dot (for example a `.receipt-*` staging
file left by an interrupted export) is ignored and counted in
`ignored_dot_files`. **Anything else that is not a receipt of this route is
reported, never skipped**: a symlink, a directory, a file not named `*.json`.
A directory with no receipt in it is a problem, so deleting the evidence
cannot read as a pass.

A file is a receipt when its name is the SHA-256 of its bytes plus `.json`,
the route's own validator accepts those bytes under that digest, and the
bytes are the committed encoding. The validator is the one `replay-*` uses;
there is no second one. The same receipt present in two directories is one
receipt.

Receipts are grouped by the `study_id` of their bundle. A study must have
exactly one original. For every replay, the parent it names must be among the
receipts given, be an original, and carry the identical bundle; then the
comparison of the two outcomes by their encoding is **recomputed**. A stored
`replay_matches_parent` that disagrees with the recomputation is a problem,
and so is a replay that does not match. A study with no replay is reported
with `"replayed": false`, which is not a problem unless the expected outcomes
require a replay.

## The report

One JSON object in the committed encoding:

```json
{"check": "export", "route": "program", "receipts": 2, "ignored_dot_files": 0,
 "expected_sha256": null, "ok": true, "problems": [],
 "studies": {"example-study": {
   "originals": [{"receipt_sha256": "…", "outcome_status": "PROGRAM_HOLDS",
                  "python": "3.12.3", "elapsed_ms": 412}],
   "replays": [{"receipt_sha256": "…", "outcome_status": "PROGRAM_HOLDS",
                "python": "3.13.1", "elapsed_ms": 398,
                "parent_receipt_sha256": "…", "matches_parent": true}],
   "replayed": true, "problems": []}}}
```

- `receipts` counts distinct admitted receipts. `expected_sha256` is the
  SHA-256 of the expected file's bytes, or null without one.
- `originals` and `replays` are sorted by digest. `python` and `elapsed_ms`
  are the receipt's `runtime` fields. `matches_parent` is the recomputed
  comparison: true, false, or null when the parent is absent, is not an
  original or has another bundle.
- `replayed` is true when at least one replay has no problem and matches.
- A problem is `{"problem": <fixed string>, "subject": <identifier>}`. The
  subject is a receipt digest, a study id, or for an entry that is not a
  receipt its path as given on the command line. File contents are never
  printed. Problems about one study are in that study's `problems`; the rest
  are in the top-level list. `ok` is true when both are empty everywhere.

| Problem | Subject | Where |
|---|---|---|
| `export directory holds no receipt` | directory | top |
| `symlink entry` | path | top |
| `not a regular .json file` | path | top |
| `file cannot be read` | path | top |
| `file exceeds the receipt byte bound` | path | top |
| `file name is not the digest of its bytes` | path | top |
| `receipt belongs to another route` | path | top |
| `receipt names another instrument version` | path | top |
| `receipt refused by the route's validator` | path | top |
| `receipt is not in the committed encoding` | path | top |
| `expected study is absent` | study id | top |
| `study has no original` | study id | study |
| `study has more than one original` | study id | study |
| `replay parent is absent` | replay digest | study |
| `replay parent is not an original` | replay digest | study |
| `replay bundle differs from its parent` | replay digest | study |
| `replay flag disagrees with the recomputed comparison` | replay digest | study |
| `replay does not match its parent` | replay digest | study |
| `study is not listed in the expected outcomes` | study id | study |
| `outcome status differs from the expected status` | original digest | study |
| `summary digest differs from the expected digest` | original digest | study |
| `study has no matching replay` | study id | study |

A changed or renamed file is `file name is not the digest of its bytes`; its
study then also loses that receipt, for example `study has no original`.

## Expected outcomes

A consumer commits this file **before** running the family. The schema
`hypersearch.expected-outcomes/v1` is closed: unknown or missing fields,
duplicate keys and wrong types are refused with exit 2. At most 1 MiB.

```json
{"schema": "hypersearch.expected-outcomes/v1", "require_replay": true,
 "studies": {"example-study": {"status": "PROGRAM_HOLDS",
   "summary_sha256": "…", "unregistered_summary_fields": ["nodes_visited"]}}}
```

- `studies` lists at least one study id. Every listed study must be present
  and no other study may be.
- `status` is an outcome status of the route (or `EXECUTION_FAILED` or
  `INCOMPLETE`). Each original of the study must have it.
- `summary_sha256`, **program route only**, is null or the SHA-256 of the
  committed encoding of the summary the program is expected to print, after
  removing the top-level keys named in `unregistered_summary_fields` (at
  most 64 distinct names). With the package:
  `digest(encode({"count": 12}))` from `hypersearch.study_json`. A name that
  the printed summary does not have changes nothing. Naming unregistered
  fields without a digest is refused, and so is a digest on another route.
- `require_replay`: when true, every study needs `"replayed": true`.

The file is the consumer's statement. The check says only whether the
receipts agree with it.

## Limits

- A receipt names the instrument version that wrote it, and the validators of
  any other version refuse it. Check an export with the version its bundles
  pin; receipts written before 0.8.0 are reported as
  `receipt names another instrument version`.
- Receipts are not signed. The check shows that the files are consistent with
  each other and with the expected file; it cannot show who wrote them. A
  digest committed elsewhere, as for `replay-*`, remains the anchor.
- The pinned core and consumer checkouts are not examined; only the receipts
  are. A chain in which a replay's parent is itself a replay is reported as
  a problem, although the instrument can produce one.
- Cooperative local filesystem only: a directory changed while it is being
  read is not defended against.

## Status — 2026-11-15

Motivation: after a family of frozen studies has run, a reviewer had to
re-check by hand that every exported receipt is intact, belongs to the
family, has one original and one matching replay, and printed what was
registered. The mechanical part of that is now one command.

Implemented with the routes' existing validators. Tests build real receipts
with synthetic consumers through all three routes and cover: an intact family
in one and in two directories; a changed byte, a renamed file, a file edited
and renamed to its new digest, a non-JSON name, non-receipt content, another
encoding, an oversized file, a symlink, a subdirectory, dot-files, an empty
directory; a receipt of another route and of another version; a replay with
an absent parent, of another bundle, of a replay, with a wrong stored flag
and with a differing outcome; two originals; every expected-outcome
difference; a closed expected file; and the real command line with its exit
codes and launch contract. Each check was removed in turn in a scratch copy
to confirm that a test fails; the table is in the pull request.

Author checks only, on Python 3.11, 3.12 and 3.13; counts are in the pull
request. Not independently reviewed. Linux only. No research executed, no
claim promoted.
