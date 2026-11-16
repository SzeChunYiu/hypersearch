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

## Implemented from this list

- **An admitted exploration route** (0.10.0, [EXPLORATION.md](EXPLORATION.md)):
  exploratory runs get non-citable receipts that `check-export` and the
  frozen routes refuse as evidence. Independent review pending.

## Planned for the frozen routes

Not implemented. All came from use of the pinned-program route on families
of studies; each is a separate change, and most need a new schema version.

- **A CPU-time limit in a v2 manifest.** The only time limit today is wall
  time, so a busy host can turn a correct computation into `INCOMPLETE`, and a
  consumer has to keep the host otherwise idle while a study runs. A limit on
  the program's CPU time would make the outcome independent of host load, so
  studies could run in parallel. The usage printed since 0.8.0 is the
  evidence for sizing it. Exit: a program that needs more wall time than CPU
  time on a loaded host still completes; one that exceeds its CPU limit is
  `INCOMPLETE` on any host.
- **A family manifest with registered predictions and stop rules.** A family
  of studies is today driven by consumer-written scripts, and its registered
  outcomes are a file checked afterwards by `check-export`. A frozen family
  manifest would name the studies, the outcome each is predicted to have and
  the rule for stopping early, and the instrument would run the family and
  report against it. Exit: a family runs from one frozen file with no
  consumer driver, and a prediction that fails is reported at the study where
  it fails.
- **A bundle digest in the expected outcomes.** `check-export` matches a
  registered outcome by `study_id` alone. An optional digest of the bundle
  (or of the program) per study would bind the outcome to what was run; the
  digest must be defined on the committed encoding, not on a consumer's file
  bytes. Exit: a receipt of another bundle under a registered id is reported.

## Priorities

Build the evidence kernel before expanding autonomy. Establish a public mathematics benchmark before adding paid or distributed infrastructure. Deliver one empirical adapter before claiming implemented domain neutrality. Preserve exploratory flexibility without allowing exploration to weaken the certifier. Maintain separate research and infrastructure queues, reserving capacity for independent review and replication.

## Measurements

Track verified useful results per total cost; false acceptance/rejection on known-answer fixtures; independently reproduced fraction; unresolved objection age; duplicate attempts; queue/review wait; recovery losses; resource-accounting uncertainty. Report denominators and unfinished work. Novelty is assessed against prior art, not inferred from unusual text or a high search score.

## Continuous work policy

Each improvement cycle inspects the current repository and open work, reads relevant primary sources, chooses one bounded unmet acceptance criterion, implements and tests a scoped PR, and records evidence and blockers. Do not duplicate open PRs, claim an unrun benchmark, auto-publish scientific claims, merge without required independent review, or copy private material. A scheduled development pass is not a continuously running scientific worker fleet.
