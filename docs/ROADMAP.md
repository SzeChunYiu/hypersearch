# Roadmap and acceptance gates

The objective is useful, reproducible discovery across domains. A completed software task is not evidence of a scientific breakthrough.

| Phase | Deliverable | Exit evidence |
|---|---|---|
| 0 — foundation | Local store, bounded mathematical search/check, CLI, CI, literature and governance | Fresh checkout demo, adversarial unit tests, reproducible certificate; limitations explicit |
| 1 — evidence kernel | Typed specs, artifact store, append-only lineage, trusted evaluator registry and immutable receipts | Changed plan/input/evaluator rejected; missing artifacts fail closed; replay yields same scoped verdict |
| 2 — mathematical discovery | Search-policy interface, counterexamples, exact bounds, proof obligations, Lean/SAT optional adapters | Known-answer and adversarial suite; independent certificate replay; no theorem overclaim; rank-three public benchmark pack |
| 3 — empirical science | Second domain adapter, preregistration, baseline/control tests, uncertainty and trial ledger | Same core runs two genuinely different domains; planted-null false acceptance measured; protected holdout audit |
| 4 — scalable workers | Authenticated service, native-session enrollment, leases/fencing, resource reservations, checkpoints, sandbox | Crash/partition/replay/rollback/overload tests at actual effect receivers; bounded recovery and queue age |
| 5 — cumulative science | Provenance graph, literature provenance, deduplication, negative results, critic-to-task loop | Every claim traceable; retractions invalidate dependent claims; unresolved objections prevent promotion |
| 6 — measured improvement | Policy portfolio and versioned evaluation program | Matched budgets/seeds, held-out families, valid-result throughput and false acceptance, independent review/rollback |
| 7 — public releases | Docs, reproducibility bundles, contributor attribution and release signing | Community can reproduce a release without private access; license/provenance audit and consumer compatibility |

## Priorities

Build the evidence kernel before expanding autonomy. Establish a public mathematics benchmark before adding paid or distributed infrastructure. Deliver one empirical adapter before claiming implemented domain neutrality. Preserve exploratory flexibility without allowing exploration to weaken the certifier. Maintain separate research and infrastructure queues, reserving capacity for independent review and replication.

## Measurements

Track verified useful results per total cost; false acceptance/rejection on known-answer fixtures; independently reproduced fraction; unresolved objection age; duplicate attempts; queue/review wait; recovery losses; resource-accounting uncertainty. Report denominators and unfinished work. Novelty is assessed against prior art, not inferred from unusual text or a high search score.

## Continuous work policy

Each improvement cycle inspects the current repository and open work, reads relevant primary sources, chooses one bounded unmet acceptance criterion, implements and tests a scoped PR, and records evidence and blockers. Do not duplicate open PRs, claim an unrun benchmark, auto-publish scientific claims, merge without required independent review, or copy private material. A scheduled development pass is not a continuously running scientific worker fleet.
