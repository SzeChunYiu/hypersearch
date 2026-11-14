# Prior systems and adoption decisions

Checked: **2026-11-14**. This is a bounded primary-source review, not an exhaustive survey or an independent reproduction of the cited results. Described capabilities are source claims unless explicitly identified as our recommendation. Adoption decisions concern design ideas; no upstream implementation was copied for this review. Integration requires checking the exact version, interfaces, and applicable license separately.

## 1. ScientistTwo — experiments and review-driven refinement

Sources: [paper](https://arxiv.org/html/2609.19644v1), [Google Cloud AI Research project](https://scientist-two.github.io/).

The system extracts limitations, generates ideas, screens on subsets, evaluates full benchmarks, performs ablations, and converts review feedback into further experiments. Its integrity audit examines score reproduction, specification compliance, reference existence, and method/code alignment. This is a Google project, distinct from AI co-scientist.

**Evidence limits:** Reported automated-review acceptance is not actual conference acceptance. The paper acknowledges approximately $3,800 per task and difficulty advancing beyond local algorithmic refinements. Existence of a reference does not establish support for an associated claim.

**Adopt:** Executable review obligations, ablations, baseline reproduction, four explicit integrity checks. **Defer:** Unbounded review loops or any claim that automated acceptance establishes publishability. Reserve independent confirmation outside adaptive screening.

## 2. AI co-scientist — asynchronous hypothesis development

Source: [Google research paper](https://arxiv.org/html/2502.18864v1).

Specialist generation, reflection, ranking, proximity, evolution, and meta-review agents operate through an asynchronous supervisor and persistent context. Hypotheses evolve through debates and tournaments.

**Evidence limits:** Ranking is a prioritization mechanism, not a proof of validity. Selected expert and experimental evaluations do not certify every generated hypothesis or transfer automatically to mathematics.

**Adopt:** Durable tasks, explicit specialist roles, persistent evidence-backed memory, hypothesis deduplication. **Defer:** Elo or agent consensus as acceptance criteria. Require domain-specific independent checks after proposal ranking.

## 3. AI Scientist-v2 — branching experiments

Sources: [official repository](https://github.com/SakanaAI/AI-Scientist-v2), [paper](https://arxiv.org/abs/2504.08066).

An experiment manager guides progressive agentic tree search and reduces dependence on manually authored templates. The workflow connects hypotheses, experiments, analysis, and manuscript drafting.

**Evidence limits:** The repository explicitly notes that broader exploration may have lower success than v1 with strong templates. Its advertised domain generalization is across machine-learning problems, not demonstrated universal science. Executing generated code needs isolation.

**Adopt:** Immutable experiment parents, branching alternatives, failed-attempt retention, bounded exploration. **Defer:** Manuscript production as the primary success metric. Measure independently verified findings per unit cost.

## 4. AlphaEvolve and FunSearch — search separate from checking

Sources: [official AlphaEvolve repository](https://github.com/google-deepmind/alphaevolve), [official FunSearch repository](https://github.com/google-deepmind/funsearch).

Both connect program generation to evaluation. The current AlphaEvolve repository includes a minimal local implementation, mathematical results, and verification material. Its matrix-multiplication work distinguishes fast floating-point optimization from rigorous rational verification. FunSearch releases construction programs and checkable objects.

**Evidence limits:** A supplied objective constrains what search can establish. FunSearch explicitly omits its production sandbox, language models, and distributed infrastructure. Finding a construction does not prove global optimality.

**Adopt:** Separate candidate producers and immutable verifiers; retain exact witnesses. **Defer:** Production integration until its operational and evaluator-security requirements pass tests. Never treat a numerical objective value alone as a theorem.

## 5. ShinkaEvolve — affordable exploration

Sources: [authors' technical overview](https://sakana.ai/shinka-evolve/), [official repository](https://github.com/SakanaAI/ShinkaEvolve).

The system combines parent sampling, novelty-based proposal filtering, and bandit-based model selection to improve program-search efficiency. It retains evaluated programs and exposes search history.

**Evidence limits:** Reported gains depend on evaluated tasks and budgets. Code-embedding distance and model novelty judgements are not scientific novelty tests. A novelty filter can discard small but important changes.

**Adopt:** Optional cost-aware provider routing and exploration policies, evaluated against fixed baselines. **Defer:** Hard novelty rejection as a universal default. Record rejected proposals and audit the filter's missed improvements.

## 6. Station — cumulative mathematical research

Sources: [official repository](https://github.com/dualverse-ai/station), [released proof and verification companions](https://dualverse.ai/station/math/).

Station models a persistent research community in which agents exchange work, inherit unfinished directions, and build shared literature. Released mathematics companions include constructions, exact checks, and proof material.

**Evidence limits:** Novelty and discovery claims here are author-reported, not independently reproduced by this review. Its README identifies clearly scorable tasks and roughly two-hour-or-shorter runs as suitable operating conditions.

**Adopt:** Attribution, persistent problem histories, independent replication tasks, certificate attachment. **Defer:** A general autonomous-community deployment until resource fairness and duplicate-work controls are measured. Shared agent literature remains untrusted until checked.

## 7. Agent Laboratory / AgentRxiv — reusable research memory

Source: [official repository](https://github.com/SamuelSchmidgall/AgentLaboratory).

Agent Laboratory connects literature review, experimentation, and reporting with optional human copilot operation. AgentRxiv enables agents to retrieve and build on earlier research.

**Evidence limits:** Availability in a shared repository does not establish correctness, novelty, or independent replication. Reusing unchecked summaries can propagate errors across otherwise separate agents.

**Adopt:** A shared claim/evidence registry with source attribution, supersession, negative results, and verification status. **Defer:** Automatic promotion of retrieved agent papers into trusted knowledge. Reports must link their supporting artifacts.

## 8. autoresearch — a small bounded experiment loop

Source: [karpathy/autoresearch official repository](https://github.com/karpathy/autoresearch).

The inspected README describes a deliberately small single-GPU training loop: the agent changes a training file, runs a fixed training-time budget, evaluates validation bits per byte, and retains or discards changes. Data preparation and evaluation are separated from the editable training file.

**Evidence limits:** This demonstrates a narrow optimization workflow. Equal wall-clock budgets do not make results hardware-independent, and repeated validation selection does not supply untouched confirmation evidence.

**Adopt:** Small editable surfaces, bounded experiments, explicit keep/discard history, protected evaluation. **Defer:** Universal discovery claims or unrestricted execution. Hypersearch must enforce permissions technically rather than relying solely on instructions.

## 9. Lean — formal proof checking

Source: [official Lean language reference: elaboration and compilation](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/).

Lean separates elaboration from a small trusted kernel that checks core proof terms. This supports a verifier boundary independent of an agent's informal explanation.

**Evidence limits:** Kernel checking concerns the formal statement and its assumptions; it does not establish correspondence to the intended natural-language question or novelty. The documentation also states that command elaboration can perform arbitrary IO. The linked validating-proofs page returned 404 during this review; it was not inspected.

**Adopt:** A future isolated proof-checking adapter with pinned toolchain, exact target statement, dependency/axiom record, and explicit permitted-assumption policy. **Defer:** Formal certification until that adapter exists and adversarial tests pass. Successful execution or textual absence of `sorry` alone is insufficient.

## 10. Temporal — recoverable execution

Source: [official workflow-execution documentation](https://docs.temporal.io/workflow-execution).

Temporal documents persistent event history and replay for recoverable workflows, with workers and activities separating orchestration from external work. It also identifies deterministic constraints and per-workflow size/throughput limits.

**Evidence limits:** Durable orchestration does not make a scientific result correct or external side effects automatically safe to repeat. This review inspected concepts, not an implementation benchmark or deployment.

**Adopt:** Event history, explicit attempts, bounded retries, idempotent result ingestion, cancellation, and recovery tests. **Defer:** A mandatory Temporal dependency until the local kernel establishes its contract and distributed load justifies the operational cost.

## Design synthesis

Hypersearch should expose one research contract to multiple discovery policies. Its trusted layer tracks questions, attempts, artifacts, verifier versions, and claims; domain adapters define what counts as evidence. Search, review, certification, and publication remain different operations.

The first implementation should establish a reproducible mathematics example and failure-path tests. Later policies should compete on fixed budgets and tasks using verified-result rate, false acceptance, reproducibility, latency, and cost. Improved prose, more agents, more commits, or more experiments alone do not demonstrate scientific progress.

Before adopting an upstream change, record its precise source version, the capability being borrowed, an acceptance test, resource impact, and rollback condition. Public integration must use public or explicitly cleared material; private deployments can consume the public interfaces without exporting their data, strategies, prompts, or results.
