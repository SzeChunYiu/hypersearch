# Architecture and trust boundaries

## Purpose

Hypersearch is a public research instrument for cumulative discovery. It separates the machinery of asking, executing, checking and preserving research from the scientific rules of a particular field. A shared workflow does not imply a universal test of truth.

## Target contracts

1. **Research specification:** question, domain, claim type, explicit assumptions, input/source versions, evaluator version, resource envelope, stopping rule and prerequisites. Freeze before execution; amendments create a new identity.
2. **Attempt:** stable task identity, parent attempt, worker/contributor lineage, lease generation, execution provenance and actual resource use. Failed attempts remain visible.
3. **Artifact:** content-addressed bytes, media/schema version, provenance and access policy. Hash identity is not authenticity or truth.
4. **Verification receipt:** exact input/plan/artifact/evaluator identities, re-derived verdict, explicit scope and failure reasons. Workers cannot select their own weaker evaluator.
5. **Claim:** precise statement and assumptions, support and counterevidence, unresolved obligations, novelty assessment and review history. Computational verification, formal proof, replication and publication are separate dimensions.
6. **Publication:** evidence bundle with references, reproducible instructions, contributions, limitations and disclosure checks. Publication never manufactures certification.

## Small trusted kernel, interchangeable discovery policies

The kernel owns admission, frozen specifications, bounded attempts and result ingestion. Policies propose actions: literature-guided hypotheses, counterexample search, program evolution, experimental trees and proof search. Domain adapters define input validation, execution and trusted verification. Scheduling ranks expected information gain or useful verified output against total cost, including review; it does not optimize paper count or positive verdicts.

The initial implementation includes a single-host SQLite task store and one built-in mathematics adapter. The CLI recomputes verification itself. The generic store only records JSON; it does not certify submitted evidence or authenticate worker names. No plugin-supplied receipt is automatically trusted. There is no network dispatcher, arbitrary-code runner, LLM provider integration, formal prover or automated publication service yet.

## Admission before persistence

The bundled CLI validates the task schema and adapter input bounds before
opening the task store. Invalid demo requests create no database, submit no
task, and acquire no earlier pending work. The adapter reuses the same pure
input validation at search time; leased specifications are revalidated before
execution. The generic store remains domain-neutral. This is cooperative CLI
admission, not authentication of arbitrary database writers. Once valid work
is acquired, execution failures remain charged and recorded.

Primary documentation consulted 2026-11-14:
[Python argparse type conversion](https://docs.python.org/3/library/argparse.html#type)
and [sqlite3 connection/transaction behavior](https://docs.python.org/3/library/sqlite3.html).
Integer parsing does not enforce adapter bounds; opening a SQLite connection
may create a file. Therefore admission precedes store construction, rather than
relying on execution failure or transaction rollback to reject bad requests.

## Ownership and recovery

One local SQLite authority serializes claims. Reclaimed tasks receive a higher fencing generation; result acceptance checks current ownership, generation and expiry. An attempt is charged when granted, including failures, lost replies and stopped or abandoned launches; a stopped launch returns its task to pending at once with its fence spent. This bounds attempts, not dollars, tokens, CPU time or external side effects. Next stages must reserve multidimensional budgets and reconcile uncertain external effects before retrying.

SQLite files must remain on one host/local filesystem. Distributed workers eventually use an authenticated service; they must not share WAL files over network storage. Clock rollback, database rollback, disk loss, malicious local edits and authenticated cross-host ownership remain unhandled production threats. External receivers must enforce fencing at their own side-effect boundary before deployment is claimed.

## Scientific judgment

A zero-sum-free sequence of length L in a specified finite group certifies the lower bound D(G) >= L+1 after exact verification. Failure to find a longer sequence proves no upper bound. This example discovers witnesses for known small instances; it is not a new theorem or an independent scientific replication. The checker uses a different algorithm, but both implementations share a project and some validation code.

Empirical adapters will require predeclared estimands, data access boundaries, baseline/negative controls, uncertainty, trial accounting and replication. Formal mathematics requires exact goal binding, pinned imports/toolchain, allowed axioms and independent proof replay. A numerical trend cannot become an unbounded theorem.

## Self-improvement

Every harness improvement is itself a study: frozen task suite and budget, baseline version, change hypothesis, adversarial checks, matched evaluation, full failures/costs, independent review, rollback. Hold out benchmark families; do not repeatedly optimize against the release test. Review objections become tracked experiments or proof obligations. Non-improvements and inconclusive comparisons remain in the record.
