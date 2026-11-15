# Consumer adoption contract v1

A research repository keeps its own registry, archive, studies and promotion policy. It consumes a pinned Hypersearch instrument; it must not duplicate the instrument or create a competing claim ledger. The first intended consumer is Davenport research. Other repositories adopt the same contract independently; organization membership alone never enrolls a consumer.

## Required checks before any instrument import

- Repository identity matches the expected upstream, and `HEAD` equals a full 40-character commit pin.
- Checkout is clean, including untracked/ignored executable source; no ambient PYTHONPATH can replace the pinned package.
- Release manifest version, API and required schema identities match the consumer pin.
- Development pins are explicitly experimental. Missing/malformed pins and incompatible versions fail closed.
- Consumer scope binds the scientific question, group and k where relevant; a valid certificate for another question is refused.

The provided Davenport adapter is a source-checkout conformance route using bundled trusted functions. It does not authenticate a malicious filesystem owner, secure Python itself, or commission generated-code execution. Its known-answer demo does not modify claims or remove promotion holds.

## Commissioning checklist

1. Run consumer registry/archive integrity checks before research. Missing archived evidence is a failure, not a metadata-only pass.
2. Run pinned clean-checkout smoke and replay its result with the declared group.
3. Exercise wrong pin, dirty source, stale/unchecked bytecode cache, wrong origin, missing/incompatible manifest and wrong task refusal. Launch through a private empty cache prefix; test imports that occur before the consumer's own gates.
4. Record exact upstream and consumer commit, commands, runtime, output digest, limitations and reviewer lineage.
5. Test an explicit pin transition and rollback using frozen fixtures; leave existing studies pinned.
6. Review and merge the adoption PR under consumer rules. Experimental smoke may be enabled while theorem promotion remains on HOLD.

## Mathematical scope

The ordinary search demo has order <=64 and sequence length <=16. The multiwise verifier supports larger ambient groups but still caps sequence length at 16 and uses exact finite computation. It checks a supplied witness, not a full frontier search. The large rank-three/multiwise programme needs scalable certificates, problem-specific completeness arguments, theorem/proof integration and independent checks. Successful conformance does not prove new mathematics or certify a manuscript.
