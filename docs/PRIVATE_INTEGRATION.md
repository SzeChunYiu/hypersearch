# Public core and private consumers

Hypersearch shares a design lineage with a private research pipeline. It is an original public implementation; no private source, datasets, results, issue text or history is imported.

| Public responsibility | Private consumer responsibility |
|---|---|
| Versioned generic task/artifact/evidence interfaces | Domain-specific data, objectives, assumptions and policy |
| Trusted generic coordination and validation primitives | Independent domain evaluator and protected validation sets |
| Public synthetic fixtures and compatibility tests | Credentials, infrastructure and operational authorization |
| Releases and migration notes | Explicit reviewed adoption of a pinned release |
| Public regression fixes | Sanitized minimal reproductions of private failures |

Migration must proceed through a contract inventory, adapter implementation in the private repository, fixture-based comparison, shadow execution, reviewed pin adoption and rollback rehearsal. The public repository must not import private packages to pass tests. Sharing a package or schema does not establish that either consumer is deployed or compatible.

Only disclose generic lessons and public synthetic examples. Review every export for provenance and license, private URLs/content, identifiers, data samples and embedded secrets. The ordinary dependency direction is public core -> private installation. There is no automatic private-to-public synchronization. No private repository is changed by the initial bootstrap.
