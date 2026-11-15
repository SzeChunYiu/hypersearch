# Shadow director design — issue #16

Scope: bounded software conformance only, frozen before tests/execution.
No research outcome, novelty or allocation-effectiveness claim.

## Two options

1. Pure frozen JSON bytes to recommendation bytes. No mutable state, Store,
   scheduler or provider access. Exact input and policy digests support replay.
   Current admission remains a separate consumer obligation.
2. Store-reading facade. Obtains tasks directly, but couples recommendations
   to mutable authority and introduces snapshot/lease questions.

Choose option 1 for this increment. No execution integration.

## Contract and deliberate limits

Closed observation, policy and recommendation schemas at v1. Observation names
consumer commit, shared declared gain/cost units and snapshot gates. Candidate
identity binds a frozen task digest. Integer costs explicitly declare execution,
verification, coordination and recovery in one comparable declared unit.
Missing/negative components or nonpositive totals refuse. Syntactic completeness
does not prove real costs were fully anticipated.

Policies are supplied order, exact rational declared gain/total cost, or seeded
SHA256 order. This last baseline is reproducible hash ordering, not a theorem of
uniform random sampling. Seed is explicit and unused seeds must be zero.
Exact finite optimal comparison needs a separately specified future model.
There is no learned prior, calibrated VOI, scientific reward or optimality claim.

Permission allowed/pending/denied/revoked, HOLD active/clear, and dependency
ready/pending/revoked are distinct. Only all-clear positive-gain candidates are
ranked. Blocked positive candidates defer if none can be recommended. A global
block defers even with no candidates. Otherwise no positive candidates stops.
These are baseline policy assumptions; stop is not scientific closure and defer
does not schedule a retry or imply that permission will return.

Input digests establish exact byte identity, not authenticity. Caller pins core
commit separately. Return immutable canonical bytes. Every output has mode shadow,
authority none, execution_allowed false. Future execution must recheck live
Store/consumer admission and exact task identity. No attempt is submitted/granted.

Tests cover closed fields, unknown policies, invalid numbers, duplicate keys/IDs,
cost completeness, frozen identities, replay/ties, all gate distinctions and
stop/defer. Independent review and consumer adoption remain separate.

## Prior-art boundary

Design audited against public residual-routing and bounded-context concepts in
[ORION at a fixed commit](https://github.com/SzeChunYiu/ORION/blob/3c7f84b8130b3316721417371e6d63b446c43c63/packages/orion-research-harness/src/orion_research_harness/research_director.py).
Its [finite VOI protocol](https://github.com/SzeChunYiu/ORION/blob/3c7f84b8130b3316721417371e6d63b446c43c63/development/orion-q-nlane-closure/N4_A_UNKNOWN_VOI_PROTOCOL.md)
has a synthetic scope, true supplied priors and myopic comparison, not general
director optimality. Consulted 2026-11-15. No source code was copied; no donor
result transfers as evidence for these policies.
