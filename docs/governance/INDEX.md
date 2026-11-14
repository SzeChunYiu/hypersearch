# Management index

| Authoritative material | Purpose | Change route |
|---|---|---|
| `governance/materials.json` | Exact tracked-path inventory: owner, role and lifecycle | Same PR as material addition/move/removal; CI rejects drift |
| `governance/release.json` | Development version, API and supported schema identities | Release/interface PR; cross-check package versions |
| `docs/governance/LIFECYCLE.md` | Layout, release, retention and adoption policy | Governance PR with relevant regression fixtures |
| `docs/governance/TWIN_DEVELOPMENT.md` | Shared invariants and improvement exchange | Contract change with consumer impact assessment |
| `docs/governance/ADOPTION.md` | Consumer contract and commissioning checklist | Interface PR plus consumer tests |
| `docs/STATUS.md` | Dated observed implementation evidence and blockers | Update from executed checks; never invent deployment |
| `docs/ROADMAP.md` and linked issues | Engineering programme and acceptance work | Scoped engineering change |
| Consumer research registry | Mathematical claims, novelty and promotion | Consumer's research-review protocol only |

Run `PYTHONPATH=src python -m hypersearch.governance .` before a PR. Add new files to Git's index before checking, so the inventory can be compared to the intended tracked tree. In CI the complete committed tree is checked. Local ignored/untracked files are outside this inventory; a consumer additionally requires a clean checkout.

Every document and script has an inventory entry. The inventory does not replace scientific provenance or make file contents correct. Git commits version the bytes; runtime artifacts need separate content digests and durable retention. No private identifiers or private counterpart links belong in this public inventory.
