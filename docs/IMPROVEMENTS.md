# Frozen improvement comparisons

The `hypersearch.finite-suite-comparison/v1` evaluator compares one baseline
and one candidate on a finite, precommitted suite. The plan binds raw source
identities, task identities, expected binary outcomes, integer weights, one
matched operation budget and a positive minimum gain. Both run records must
retain every planned case, including failures, timeouts and cases not run.

The evaluator is pure. It matches the plan's evaluator digest against a local
bundle of `improvement.py` and `study_json.py`, then checks syntax, digests and
declared identities in the supplied records. It does not attest that a named
baseline or candidate executed, validate expected labels, schedule work, update
a claim registry, remove a hold or promote a release. Its result has
`promotion_authority: none`, `execution_attestation: none`, and explicit source
and label validation flags. Costs, case outcomes and candidate source identities
are producer declarations. A commissioning consumer owns execution, oracle
validation, attestation and any decision made after evaluation.

## Outcomes

- `ACCEPT`: according to the supplied records, both runs are complete within the
  same frozen budget, the candidate introduces no case regression or false
  acceptance on the finite suite, and its correct-weight gain reaches the
  threshold.
- `REJECT`: any reported false acceptance, case regression or known budget
  overrun rejects even if another case is incomplete. A complete comparison
  below the positive threshold also rejects. An unchanged/no-benefit control
  therefore rejects.
- `INCONCLUSIVE`: absent a known rejection above, execution is incomplete or any
  cost is unknown. All case outcomes remain in the evaluation record.
- malformed, selectively reported, duplicated, unplanned or identity-mismatched
  evidence is refused instead of assigned a scientific verdict.

`ACCEPT` is only the declared finite benchmark criterion; it is not research,
theorem, release or claim acceptance. Each suite must include both positive and
negative controls, but a finite result establishes no population error rate.
The binary expected outcome is intentionally generic. Domain adapters decide
what counts as `ACCEPT` or `REJECT` and must freeze that interpretation before
execution. Existing studies retain their original evaluators and pins. Changing
an evaluator, suite, baseline, budget or threshold creates a new plan identity;
it is not an in-place upgrade.

## API

Call `hypersearch.improvement.evaluate(plan_bytes, baseline_run_bytes,
candidate_run_bytes, expected_plan_sha256)`. It returns canonical JSON bytes.
The closed schemas are `hypersearch.improvement-plan/v1`,
`hypersearch.improvement-run/v1` and `hypersearch.improvement-evaluation/v1`.

The conformance tests include material improvement, identical/no-benefit and
regression controls, a false acceptance hidden inside aggregate improvement,
budget overrun, timeout, failure, unknown cost, selective reporting, duplicate
identities, type confusion, order invariance and deterministic replay.

This is a software comparison instrument, not evidence that autonomous research
improves scientific discovery. A public consumer qualification must bind its
own source commits and publish its complete plan and run records before claiming
improvement on that declared finite benchmark. It still cannot claim improved
scientific discovery from this gate alone.
