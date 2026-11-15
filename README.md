# Hypersearch

**A public research harness for reproducible, cumulative scientific discovery.**

Hypersearch is being developed into a domain-neutral system that connects research questions, bounded attempts, verifiable artifacts and carefully scoped claims. Discovery agents may propose many ideas; acceptance depends on evidence appropriate to the domain.

**Current status: local foundation prototype, not a deployed autonomous scientist.** It includes a durable task queue and a working mathematics demonstration. There is no model launcher, distributed service, generated-code sandbox, formal prover, or automated scientific publication pipeline yet.

## Run the foundation

Python 3.11+; runtime uses only the standard library. No API key or private repository is needed.

```sh
git clone https://github.com/SzeChunYiu/hypersearch.git
cd hypersearch
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m hypersearch demo --db /tmp/hypersearch.sqlite
PYTHONPATH=src python -m hypersearch status --db /tmp/hypersearch.sqlite
```

Optionally install with `python -m pip install -e .` to use the `hypersearch` command.

The demo finds a zero-sum-free sequence in `C2 × C2 × C2`, then checks every nonempty indexed subset with a distinct algorithm. Its witness establishes **D(C2 × C2 × C2) ≥ 4**. This reproduces a known small example; it does not claim a new theorem, an upper bound, formal proof or independent-team replication.

```sh
PYTHONPATH=src python -m hypersearch demo --db /tmp/hypersearch.sqlite --moduli 2 2 3 --max-steps 5000
```

Group rank is limited to 3, order to 64, witness length to 16 and search to 100,000 steps. A truncated search may still yield a valid lower-bound witness. The SQLite store preserves completed work: repeating the identical task does not rerun it. It charges each acquisition against a fixed attempt budget, including expired attempts. `--budget` must match the database's original value. The demo acquires only its exact submitted task; unrelated pending work is untouched.

To replay a certificate, save the `certificate` object from demo JSON to `certificate.json`, then run:

```sh
PYTHONPATH=src python -m hypersearch verify certificate.json --moduli 2 2 2
```

## What is implemented

- Frozen task specifications and content digests.
- Transactional local claims, lease generations and stale-result refusal.
- Persistent attempt budgets, event records and one-result-per-task storage.
- Bounded zero-sum witness search and independently recomputed finite certificates.
- Task-bound verification, source hashes and explicit evidence scope in CLI output.
- Adversarial tests and a Python-version CI matrix.

The store records arbitrary JSON results; **a stored result is not scientific acceptance**. Worker names are cooperative labels, not authenticated identities. Current budget units are attempts, not tokens, money or CPU time. Local file access can modify the database; this is not a hostile-worker security boundary.

## Direction

| Layer | Responsibility |
|---|---|
| Research kernel | Specifications, lineage, ownership, resource limits and evidence contracts |
| Discovery policies | Literature synthesis, experimental trees, evolution, counterexamples and proof search |
| Domain adapters | Mathematical or empirical semantics, trusted checks and scoped conclusions |
| Review and publication | Independent assessment, objections, reproducibility and attribution |
| Improvement programme | Benchmark the harness itself against frozen tasks and full costs |

The public core will remain usable without private infrastructure. Private research pipelines can consume versioned interfaces through their own adapters and pinned releases. No private source or research results are included.

Start with [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), [implementation status](docs/STATUS.md), [literature review](docs/LITERATURE.md), and [private-consumer boundary](docs/PRIVATE_INTEGRATION.md). Contribution rules are in [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

MIT licensed. External projects retain their own licenses; references do not imply code reuse or endorsement.

## Governed adoption (0.4.0 development)

Run `PYTHONPATH=src python -m hypersearch.governance .` to check exact tracked-material ownership, lifecycle, version consistency and immutable CI action references. See the [management index](docs/governance/INDEX.md), [consumer contract](docs/governance/ADOPTION.md) and [twin development protocol](docs/governance/TWIN_DEVELOPMENT.md). Development pins remain experimental until consumer commissioning and independent release review.

The bounded multiwise verifier checks supplied witnesses for `D_k`, preserving disjointness and multiplicity:

```sh
PYTHONPATH=src python -m hypersearch verify-multiwise examples/multiwise-c2-k2.json --moduli 2 --k 2
```

This three-term sequence has at most one disjoint zero-sum subsequence, establishing only `D_2(C2) >= 4`. The verifier accepts ambient groups of order up to 1,000,000 but sequences of at most 16 terms; it is not the solver for the full frontier programme. A consumer's claim registry and promotion HOLD remain authoritative.

## Frozen supplied-certificate route

Development 0.3.0 adds run-study and externally digest-bound replay-study, using
the existing Store and only bundled bounded verifiers. See
[operation/qualification](docs/STUDIES.md) and [schemas](docs/STUDY_CONTRACT.md).
Consumer claim authority and promotion holds remain separate.

## Frozen external expert reports

Development 0.4.0 adds registered review tasks, persisted grants before native
session handoff, and lease-bound authored reports. See [review protocol](docs/REVIEWS.md).
All report receipts remain NOT_FORMALLY_VERIFIED with no claim authority.

## Shadow recommendations — 0.5.0 development

The pure [director API](docs/DIRECTOR.md) ranks frozen candidate declarations
without Store access or execution authority. It provides supplied-order, declared
gain/cost and seeded-hash-order baselines. These are hypothetical scores, not
calibrated VOI, scientific acceptance or evidence of optimal allocation.

## Exhaustive census tasks — 0.6.0 development

`run-census` counts, exhaustively and through the same frozen route, the
sequences of a given length over a small group that avoid zero-sums of chosen
lengths. See [census tasks](docs/CENSUS.md). A count of zero is one
implementation's finite computation, not a proof.

## Pinned-program tasks — 0.7.0 development

`run-program` runs one program committed by the consumer, bound by hash, in an
isolated interpreter under the same frozen route, and records its small JSON
output with a receipt and a replay. The instrument does not check the
program's logic. See [pinned programs](docs/PROGRAMS.md).
